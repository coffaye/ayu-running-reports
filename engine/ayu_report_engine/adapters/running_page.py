"""Adapter for the public running_page JSON and SQLite representations."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from ..context import DailyRunContext, SourceEvidence, parse_duration_seconds
from ..errors import DataMismatchError, DataSourceError
from ..identity import normalize_run_id
from ..version import ENGINE_VERSION

ADAPTER_VERSION = "running-page-v1"


def _required_text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DataSourceError(f"missing required text field: {key}")
    return value.strip()


def _optional_number(row: Mapping[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataSourceError(f"field must be numeric or null: {key}")
    return float(value)


def _normalize_sport(value: str) -> str:
    lowered = value.strip().lower()
    return "running" if lowered in {"run", "running"} else lowered


def _build_context(
    row: Mapping[str, Any],
    *,
    source_type: str,
    source_ref: str,
) -> DailyRunContext:
    run_id = normalize_run_id(row.get("run_id"))
    start_local = _required_text(row, "start_date_local")
    local_date = start_local[:10]
    try:
        datetime.strptime(local_date, "%Y-%m-%d")
    except ValueError as exc:
        raise DataSourceError(f"invalid start_date_local: {start_local!r}") from exc

    distance_m = _optional_number(row, "distance")
    if distance_m is None:
        raise DataSourceError("distance is required")
    moving_time = parse_duration_seconds(row.get("moving_time"))
    elapsed_time = parse_duration_seconds(row.get("elapsed_time"))
    if moving_time is None and elapsed_time is None:
        raise DataSourceError("moving_time or elapsed_time is required")

    average_speed = _optional_number(row, "average_speed")
    average_pace = None
    if average_speed is not None and average_speed > 0:
        average_pace = 1000 / average_speed

    evidence = SourceEvidence(
        source_type=source_type,
        source_ref=source_ref,
        adapter_version=ADAPTER_VERSION,
        captured_at=None,
        fields=(
            "runId",
            "localDate",
            "startDatetimeLocal",
            "sport",
            "distanceM",
            "movingTimeSec",
            "elapsedTimeSec",
            "displayDurationSource",
            "averageSpeedMps",
            "averageHrBpm",
            "ascentM",
        ),
    )
    return DailyRunContext(
        run_id=run_id,
        local_date=local_date,
        start_datetime_local=start_local,
        timezone=None,
        timezone_source="unknown",
        sport=_normalize_sport(_required_text(row, "type")),
        subtype=row.get("subtype") if isinstance(row.get("subtype"), str) else None,
        title=row.get("name") if isinstance(row.get("name"), str) and row.get("name") else None,
        distance_m=distance_m,
        timer_time_sec=None,
        elapsed_time_sec=elapsed_time,
        moving_time_sec=moving_time,
        display_duration_source="moving_time" if moving_time is not None else "elapsed_time",
        average_speed_mps=average_speed,
        average_pace_sec_per_km=average_pace,
        average_hr_bpm=_optional_number(row, "average_heartrate"),
        ascent_m=_optional_number(row, "elevation_gain"),
        structured_workout=None,
        workout_intent="unknown",
        evidence=(evidence,),
        engine_version=ENGINE_VERSION,
    )


def _read_json(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise DataSourceError(f"cannot read activities JSON: {path.name}") from exc
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise DataSourceError("activities JSON must be an array of objects")
    return value


def _find_json_row(rows: list[dict[str, Any]], run_id: str) -> dict[str, Any] | None:
    for row in rows:
        try:
            if normalize_run_id(row.get("run_id")) == run_id:
                return row
        except Exception:
            continue
    return None


def _read_sqlite(path: Path, run_id: str) -> dict[str, Any] | None:
    if not path.exists():
        raise DataSourceError(f"SQLite source does not exist: {path.name}")
    try:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM activities WHERE run_id = ?", (int(run_id),)
        ).fetchone()
        return dict(row) if row is not None else None
    except (OSError, sqlite3.Error, OverflowError) as exc:
        raise DataSourceError(f"cannot read activities SQLite: {path.name}") from exc
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass


def _assert_consistent(json_row: Mapping[str, Any], sqlite_row: Mapping[str, Any]) -> None:
    comparisons = {
        "run_id": (json_row.get("run_id"), sqlite_row.get("run_id")),
        "distance": (json_row.get("distance"), sqlite_row.get("distance")),
        "moving_time": (
            parse_duration_seconds(json_row.get("moving_time")),
            parse_duration_seconds(sqlite_row.get("moving_time")),
        ),
        "average_speed": (json_row.get("average_speed"), sqlite_row.get("average_speed")),
        "average_heartrate": (
            json_row.get("average_heartrate"),
            sqlite_row.get("average_heartrate"),
        ),
        "elevation_gain": (json_row.get("elevation_gain"), sqlite_row.get("elevation_gain")),
    }
    for field, (left, right) in comparisons.items():
        if left is None and right is None:
            continue
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            if abs(float(left) - float(right)) <= 1e-3:
                continue
        elif left == right:
            continue
        raise DataMismatchError(f"JSON/SQLite mismatch for {field}")


def load_running_page_context(
    json_path: str | Path,
    sqlite_path: str | Path | None,
    run_id: object,
) -> DailyRunContext:
    """Load JSON first, validate against SQLite, and fall back safely.

    The public JSON is the normal primary source. SQLite is used as a fallback
    when JSON is unavailable/malformed and as a consistency check when both
    records exist. Route polylines and location fields are intentionally ignored.
    """

    normalized_id = normalize_run_id(run_id)
    json_source = Path(json_path)
    sqlite_source = Path(sqlite_path) if sqlite_path is not None else None
    json_row: dict[str, Any] | None = None
    json_error: DataSourceError | None = None
    try:
        json_row = _find_json_row(_read_json(json_source), normalized_id)
    except DataSourceError as exc:
        json_error = exc

    sqlite_row = (
        _read_sqlite(sqlite_source, normalized_id)
        if sqlite_source is not None and sqlite_source.exists()
        else None
    )
    if json_row is not None:
        if sqlite_row is not None:
            _assert_consistent(json_row, sqlite_row)
        return _build_context(
            json_row,
            source_type="running_page-json",
            source_ref=json_source.name,
        )
    if sqlite_row is not None:
        return _build_context(
            sqlite_row,
            source_type="running_page-sqlite",
            source_ref=sqlite_source.name if sqlite_source else None,
        )
    if json_error is not None:
        raise json_error
    raise DataSourceError(f"run_id not found in running_page sources: {normalized_id}")
