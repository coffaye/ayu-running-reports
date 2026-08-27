"""Explicit live low/high benchmark; never runs as part of tests or imports."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys

from .adapters.fit import context_from_fit_messages
from .adapters.running_page import load_running_page_context
from .deepseek import DeepSeekAnalyzer, DeepSeekConfig

RUBRIC_MAX = {
    "factual_grounding": 25,
    "no_hallucinated_metrics": 20,
    "workout_interpretation": 15,
    "evidence_quality": 15,
    "shadowrunner_quality": 10,
    "recommendation_quality": 10,
    "uncertainty_handling": 5,
}


def _contexts(fixtures: Path):
    raw = json.loads((fixtures / "fit_messages.json").read_text(encoding="utf-8"))
    raw["session_mesgs"][0]["start_time"] = datetime(
        2030, 3, 4, 22, 0, tzinfo=timezone.utc
    )
    case_a = dict(raw)
    case_a["workout_mesgs"] = []
    case_a["workout_step_mesgs"] = []
    case_c = load_running_page_context(fixtures / "activities.json", None, "1900000000000")
    return {
        "A_basic_run": context_from_fit_messages(case_a, source_ref="sanitized-case-a.fit"),
        "B_long_workout": context_from_fit_messages(raw, source_ref="sanitized-case-b.fit"),
        "C_missing_metrics": case_c,
    }


def run_live_benchmark(fixtures: Path, output: Path) -> int:
    config = DeepSeekConfig.from_env()
    if not config.api_key:
        print(json.dumps({"status": "not_run", "reason": "DEEPSEEK_API_KEY is not configured"}))
        return 2
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
            try:
                result = DeepSeekAnalyzer(run_config).analyze_with_metadata(context)
                rows.append(
                    {
                        "case": case_name,
                        "effort": effort,
                        "status": "validated",
                        "metadata": result.metadata.to_dict(),
                        "rubric": {key: None for key in RUBRIC_MAX},
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "case": case_name,
                        "effort": effort,
                        "status": "failed",
                        "errorCategory": getattr(exc, "category", "unexpected"),
                    }
                )
    payload = {"rubricMax": RUBRIC_MAX, "results": rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "output": str(output), "runs": len(rows)}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explicit DeepSeek low/high benchmark")
    parser.add_argument("--live", action="store_true", help="required acknowledgement for network calls")
    parser.add_argument("--fixtures", type=Path, default=Path(__file__).parents[1] / "tests" / "fixtures")
    parser.add_argument("--output", type=Path, default=Path("deepseek-benchmark.json"))
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("pass --live to make benchmark network calls")
    return run_live_benchmark(args.fixtures, args.output)


if __name__ == "__main__":
    sys.exit(main())
