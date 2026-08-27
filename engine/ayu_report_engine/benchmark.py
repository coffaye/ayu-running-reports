"""Explicit live smoke test and low/high benchmark; never runs on import."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .adapters.fit import context_from_fit_messages
from .adapters.running_page import load_running_page_context
from .deepseek import DeepSeekAnalyzer, DeepSeekConfig, DeepSeekError
from .quality import RUBRIC_MAX, score_report
from .render import render_html
from .version import PROMPT_VERSION

# Official DeepSeek V4 Flash list prices, USD per 1M tokens. Benchmark costs
# use cache-miss input as the conservative assumption; cache-hit input is also
# recorded so the estimate can be recalculated without rerunning requests.
PRICING_USD_PER_MILLION = {
    "input_cache_hit": 0.0028,
    "input_cache_miss": 0.14,
    "output": 0.28,
}


def _contexts(fixtures: Path):
    raw = json.loads((fixtures / "fit_messages.json").read_text(encoding="utf-8"))
    raw["session_mesgs"][0]["start_time"] = datetime(
        2030, 3, 4, 22, 0, tzinfo=timezone.utc
    )
    case_a_raw = dict(raw)
    case_a_raw["workout_mesgs"] = []
    case_a_raw["workout_step_mesgs"] = []
    case_a = context_from_fit_messages(case_a_raw, source_ref="sanitized-case-a.fit")
    case_c = load_running_page_context(fixtures / "activities.json", None, "1900000000000")
    return {
        "A_basic_run": case_a,
        "B_long_workout": context_from_fit_messages(raw, source_ref="sanitized-case-b.fit"),
        "C_missing_metrics": case_c,
    }


def _smoke_context(fixtures: Path):
    """Derive the smallest useful context from the fixture, without new facts."""

    source = _contexts(fixtures)["A_basic_run"]
    return replace(
        source,
        title=None,
        average_speed_mps=None,
        average_pace_sec_per_km=None,
        average_hr_bpm=None,
        max_hr_bpm=None,
        cadence_raw_value=None,
        cadence_raw_unit=None,
        cadence_raw_field=None,
        cadence_raw_message=None,
        cadence_raw_origin=None,
        cadence_normalized_spm=None,
        stride_m=None,
        power_w=None,
        ascent_m=None,
        laps=None,
        splits=None,
        training_effect_aerobic=None,
        training_effect_anaerobic=None,
        training_load_peak=None,
        recovery_percent=None,
        recovery_hours=None,
        running_fitness=None,
        evidence=(),
    )


def _cost(metadata: dict[str, Any]) -> dict[str, float | None]:
    input_tokens = metadata.get("inputTokens")
    output_tokens = metadata.get("outputTokens")
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return {"cacheMissUsd": None, "cacheHitUsd": None}
    return {
        "cacheMissUsd": round(
            input_tokens / 1_000_000 * PRICING_USD_PER_MILLION["input_cache_miss"]
            + output_tokens / 1_000_000 * PRICING_USD_PER_MILLION["output"],
            8,
        ),
        "cacheHitUsd": round(
            input_tokens / 1_000_000 * PRICING_USD_PER_MILLION["input_cache_hit"]
            + output_tokens / 1_000_000 * PRICING_USD_PER_MILLION["output"],
            8,
        ),
    }


def _error_payload(exc: Exception) -> dict[str, Any]:
    data: dict[str, Any] = {
        "status": "failed",
        "errorCategory": getattr(exc, "category", "unexpected"),
    }
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        data["httpStatus"] = status_code
    return data


def run_live_smoke(fixtures: Path, config: DeepSeekConfig) -> dict[str, Any]:
    """Make exactly one explicit low-effort request and return safe metadata."""

    if not config.api_key:
        return {"status": "not_run", "reason": "DEEPSEEK_API_KEY is not configured"}
    analyzer = DeepSeekAnalyzer(
        DeepSeekConfig(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            reasoning_effort="low",
            max_output_tokens=config.max_output_tokens,
            timeout_seconds=config.timeout_seconds,
        )
    )
    try:
        result = analyzer.analyze_with_metadata(_smoke_context(fixtures))
    except DeepSeekError as exc:
        return {
            **_error_payload(exc),
            "endpoint": analyzer.endpoint,
            "model": analyzer.config.model,
            "reasoningEffort": analyzer.config.reasoning_effort,
            "promptVersion": PROMPT_VERSION,
            "validation": {"schema": False, "semantic": False},
        }
    metadata = result.metadata.to_dict()
    return {
        "status": "success",
        "endpoint": analyzer.endpoint,
        "model": analyzer.config.model,
        "reasoningEffort": analyzer.config.reasoning_effort,
        "promptVersion": PROMPT_VERSION,
        "metadata": metadata,
        "cost": _cost(metadata),
        "validation": {"schema": True, "semantic": True},
    }


def run_live_benchmark(
    fixtures: Path,
    output: Path,
    *,
    report_dir: Path | None = None,
) -> int:
    config = DeepSeekConfig.from_env(load_local_files=True)
    if not config.api_key:
        print(json.dumps({"status": "not_run", "reason": "DEEPSEEK_API_KEY is not configured"}))
        return 2

    smoke_path = output.parent / "smoke.json"
    smoke: dict[str, Any] | None = None
    try:
        candidate = json.loads(smoke_path.read_text(encoding="utf-8"))
        if (
            isinstance(candidate, dict)
            and candidate.get("status") == "success"
            and candidate.get("promptVersion") == PROMPT_VERSION
            and candidate.get("model") == config.model
        ):
            smoke = candidate
    except (OSError, json.JSONDecodeError):
        smoke = None
    if smoke is None:
        smoke = run_live_smoke(fixtures, config)
    if smoke.get("status") != "success":
        payload = {
            "status": "smoke_failed",
            "smoke": smoke,
            "rubricMax": RUBRIC_MAX,
            "pricingUsdPerMillion": PRICING_USD_PER_MILLION,
            "results": [],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "smoke_failed", "output": str(output)}))
        return 3

    report_dir = report_dir or output.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for case_name, context in _contexts(fixtures).items():
        for effort in ("low", "high"):
            run_config = DeepSeekConfig(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.model,
                reasoning_effort=effort,
                max_output_tokens=config.max_output_tokens,
                timeout_seconds=config.timeout_seconds,
            )
            analyzer = DeepSeekAnalyzer(run_config)
            try:
                result = analyzer.analyze_with_metadata(context)
                metadata = result.metadata.to_dict()
                html_path = report_dir / f"{case_name}_{effort}.html"
                html_path.write_text(render_html(result.report, context), encoding="utf-8")
                rows.append(
                    {
                        "case": case_name,
                        "effort": effort,
                        "status": "validated",
                        "metadata": metadata,
                        "validation": {"schema": True, "semantic": True},
                        "cost": _cost(metadata),
                        "quality": score_report(result.report, context),
                        "report": result.report.to_dict(),
                        "htmlPath": str(html_path),
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "case": case_name,
                        "effort": effort,
                        **_error_payload(exc),
                        "validation": {"schema": False, "semantic": False},
                    }
                )
    payload = {
        "status": "completed",
        "smoke": smoke,
        "rubricMax": RUBRIC_MAX,
        "pricingUsdPerMillion": PRICING_USD_PER_MILLION,
        "pricingAssumption": "cache-miss input for conservative estimate; output uses provider output_tokens",
        "results": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "output": str(output), "runs": len(rows)}))
    return 0 if all(row.get("status") == "validated" for row in rows) else 4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explicit DeepSeek smoke and low/high benchmark")
    parser.add_argument("--live", action="store_true", help="required acknowledgement for network calls")
    parser.add_argument("--fixtures", type=Path, default=Path(__file__).parents[1] / "tests" / "fixtures")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parents[1] / ".benchmark" / "deepseek-benchmark.json",
    )
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("pass --live to make benchmark network calls")
    return run_live_benchmark(args.fixtures, args.output, report_dir=args.report_dir)


if __name__ == "__main__":
    sys.exit(main())
