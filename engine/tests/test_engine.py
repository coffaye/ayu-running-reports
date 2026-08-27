from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ENGINE_ROOT = Path(__file__).parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from ayu_report_engine.adapters.fit import context_from_fit_messages
from ayu_report_engine.adapters.running_page import load_running_page_context
from ayu_report_engine.analysis import FixtureAnalyzer
from ayu_report_engine.errors import (
    DataMismatchError,
    DataSourceError,
    IdentityError,
    SchemaValidationError,
)
from ayu_report_engine.identity import normalize_run_id, run_id_from_datetime
from ayu_report_engine.render import render_html
from ayu_report_engine.report import validate_structured_report


FIXTURES = Path(__file__).parent / "fixtures"


class EngineTests(unittest.TestCase):
    def test_same_day_runs_have_distinct_identities(self) -> None:
        rows = json.loads((FIXTURES / "activities.json").read_text(encoding="utf-8"))
        self.assertEqual(rows[0]["start_date_local"][:10], rows[1]["start_date_local"][:10])
        self.assertNotEqual(str(rows[0]["run_id"]), str(rows[1]["run_id"]))
        self.assertEqual(normalize_run_id(rows[0]["run_id"]), "1900000000000")

    def test_running_page_json_keeps_missing_metrics_as_null(self) -> None:
        context = load_running_page_context(FIXTURES / "activities.json", None, "1900000000000")
        self.assertIsNone(context.average_hr_bpm)
        self.assertIsNone(context.power_w)
        self.assertEqual(context.ascent_m, 0.0)
        self.assertIsNone(context.structured_workout)
        self.assertEqual(context.workout_intent, "unknown")
        self.assertIsNone(context.timezone)
        self.assertEqual(context.timezone_source, "unknown")

    def test_running_page_sqlite_fallback_and_zero_vs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "data.db"
            db = sqlite3.connect(db_path)
            db.execute(
                "CREATE TABLE activities (run_id INTEGER PRIMARY KEY, name TEXT, distance FLOAT, moving_time TEXT, elapsed_time TEXT, type TEXT, subtype TEXT, start_date TEXT, start_date_local TEXT, location_country TEXT, summary_polyline TEXT, average_heartrate FLOAT, average_speed FLOAT, elevation_gain FLOAT)"
            )
            db.execute(
                "INSERT INTO activities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (1900000000000, "", 5000, "1970-01-01 00:30:00", None, "Run", "generic", "2030-03-04 22:00:00", "2030-03-05 06:00:00", "", None, None, 2.777777, 0),
            )
            db.commit()
            db.close()
            malformed = Path(directory) / "activities.json"
            malformed.write_text("{bad", encoding="utf-8")
            context = load_running_page_context(malformed, db_path, 1900000000000)
            self.assertEqual(context.moving_time_sec, 1800)
            self.assertEqual(context.display_duration_source, "moving_time")
            self.assertEqual(context.ascent_m, 0.0)

    def test_json_sqlite_mismatch_is_not_silently_merged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "data.db"
            db = sqlite3.connect(db_path)
            db.execute("CREATE TABLE activities (run_id INTEGER PRIMARY KEY, name TEXT, distance FLOAT, moving_time TEXT, elapsed_time TEXT, type TEXT, subtype TEXT, start_date TEXT, start_date_local TEXT, location_country TEXT, summary_polyline TEXT, average_heartrate FLOAT, average_speed FLOAT, elevation_gain FLOAT)")
            db.execute("INSERT INTO activities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (1900000000000, "", 5100, "0:30:00", None, "Run", "generic", "2030-03-04 22:00:00", "2030-03-05 06:00:00", "", None, None, 2.777777, 0))
            db.commit(); db.close()
            with self.assertRaises(DataMismatchError):
                load_running_page_context(FIXTURES / "activities.json", db_path, 1900000000000)

    def test_malformed_json_without_fallback_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "activities.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(DataSourceError):
                load_running_page_context(path, None, 1900000000000)

    def test_fit_fixture_reads_only_observed_metrics(self) -> None:
        raw = json.loads((FIXTURES / "fit_messages.json").read_text(encoding="utf-8"))
        raw["session_mesgs"][0]["start_time"] = datetime(2030, 3, 4, 22, 0, tzinfo=timezone.utc)
        context = context_from_fit_messages(raw)
        self.assertEqual(context.run_id, run_id_from_datetime(raw["session_mesgs"][0]["start_time"]))
        self.assertEqual(context.local_date, "2030-03-04")
        self.assertEqual(context.timezone, "UTC")
        self.assertEqual(context.timezone_source, "source")
        self.assertEqual(context.power_w, 240.0)
        self.assertEqual(context.timer_time_sec, 3595.0)
        self.assertEqual(context.elapsed_time_sec, 3600.0)
        self.assertEqual(context.display_duration_source, "timer_time")
        self.assertEqual(context.cadence_raw_value, 88.0)
        self.assertEqual(context.cadence_raw_unit, "strides/min")
        self.assertIsNone(context.cadence_normalized_spm)
        context_json = context.to_dict()
        self.assertNotIn("durationSec", context_json)
        self.assertNotIn("cadenceSpm", context_json)
        self.assertEqual(context.ascent_m, 0.0)
        self.assertEqual(context.structured_workout["name"], "匿名结构化课表")
        self.assertEqual(context.workout_intent, "structured")
        self.assertEqual(len(context.laps or ()), 1)

    def test_fit_reimport_identity_is_deterministic(self) -> None:
        raw = json.loads((FIXTURES / "fit_messages.json").read_text(encoding="utf-8"))
        start = datetime(2030, 3, 4, 22, 0, tzinfo=timezone.utc)
        raw["session_mesgs"][0]["start_time"] = start
        first = context_from_fit_messages(raw)
        second = context_from_fit_messages(raw)
        self.assertEqual(first.run_id, second.run_id)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_fit_missing_workout_is_unknown_not_free_run(self) -> None:
        raw = json.loads((FIXTURES / "fit_messages.json").read_text(encoding="utf-8"))
        raw["session_mesgs"][0]["start_time"] = datetime(2030, 3, 4, 22, 0, tzinfo=timezone.utc)
        raw["workout_mesgs"] = []
        raw["workout_step_mesgs"] = []
        context = context_from_fit_messages(raw)
        self.assertIsNone(context.structured_workout)
        self.assertEqual(context.workout_intent, "unknown")

    def test_invalid_identity_rejected(self) -> None:
        for value in (None, "", "-1", 0, True, 1.5):
            with self.subTest(value=value):
                with self.assertRaises(IdentityError):
                    normalize_run_id(value)

    def test_fixture_analyzer_and_structured_schema(self) -> None:
        context = load_running_page_context(FIXTURES / "activities.json", None, 1900000000000)
        report = FixtureAnalyzer().analyze(context)
        validate_structured_report(report.to_dict())
        self.assertIsNone(report.completion["score"])
        self.assertIsNone(report.completion["trainingType"])

    def test_structured_schema_rejects_invalid_score(self) -> None:
        context = load_running_page_context(FIXTURES / "activities.json", None, 1900000000000)
        report = FixtureAnalyzer().analyze(context).to_dict()
        report["completion"]["score"] = 11
        with self.assertRaises(SchemaValidationError):
            validate_structured_report(report)

    def test_renderer_is_deterministic_and_contains_canvas_export(self) -> None:
        context = load_running_page_context(FIXTURES / "activities.json", None, 1900000000000)
        report = FixtureAnalyzer().analyze(context)
        first = render_html(report, context)
        second = render_html(report, context)
        self.assertEqual(first, second)
        self.assertIn("下载 PNG", first)
        self.assertIn("canvas.toBlob", first)
        self.assertIn("EXPORT_WIDTH = 2480", first)
        self.assertIn("MIN_HEIGHT = 3508", first)
        self.assertIn("TODAY 今日结论", first)
        self.assertNotIn("DEEPSEEK_API_KEY", first)
        self.assertNotIn("COROS_PASSWORD", first)
        self.assertNotIn("summary_polyline", first)

    def test_renderer_has_responsive_layout_and_html_footer_only(self) -> None:
        context = load_running_page_context(FIXTURES / "activities.json", None, 1900000000000)
        report = FixtureAnalyzer().analyze(context)
        html = render_html(report, context)
        self.assertIn("@media (max-width:800px)", html)
        self.assertIn("<footer>Ayu Running</footer>", html)
        self.assertIn("measuredBottom", html)
        self.assertIn("canvasText", html)

    def test_renderer_summarizes_collection_evidence_without_raw_objects(self) -> None:
        raw = json.loads((FIXTURES / "fit_messages.json").read_text(encoding="utf-8"))
        raw["session_mesgs"][0]["start_time"] = datetime(2030, 3, 4, 22, 0, tzinfo=timezone.utc)
        context = context_from_fit_messages(raw)
        report = FixtureAnalyzer().analyze(context)
        report = replace(
            report,
            evidence=(
                {"metricRef": "summary.lapSummary", "interpretation": "存在分圈摘要。"},
            ),
        )
        html = render_html(report, context)
        self.assertIn("1 个分圈", html)
        self.assertNotIn("averageHrBpm", html)
        self.assertNotIn("None", html)
        self.assertNotIn("[object Object]", html)


if __name__ == "__main__":
    unittest.main()
