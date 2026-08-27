"""Small offline CLI used by local tests and future Actions."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .adapters.fit import context_from_fit_bytes
from .adapters.running_page import load_running_page_context
from .analysis import FixtureAnalyzer
from .deepseek import DeepSeekAnalyzer, DeepSeekConfig, DeepSeekError
from .render import render_html


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render an offline Ayu Running report")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--sqlite", type=Path)
    parser.add_argument("--fit", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--analyzer",
        choices=("fixture", "deepseek"),
        default="fixture",
        help="fixture is offline/default; deepseek is an explicit network call",
    )
    parser.add_argument("--reasoning-effort", choices=("none", "minimal", "low", "medium", "high", "xhigh", "max"))
    parser.add_argument("--max-output-tokens", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.fit:
        context = context_from_fit_bytes(args.fit.read_bytes(), source_ref=args.fit.name)
    elif args.json:
        context = load_running_page_context(args.json, args.sqlite, args.run_id)
    else:
        raise SystemExit("one of --json or --fit is required")
    if args.analyzer == "deepseek":
        # A local dotenv file is consulted only after explicit analyzer choice;
        # fixture mode and normal imports remain entirely offline.
        config = DeepSeekConfig.from_env(load_local_files=True)
        if args.reasoning_effort:
            config = DeepSeekConfig(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.model,
                reasoning_effort=args.reasoning_effort,
                max_output_tokens=args.max_output_tokens or config.max_output_tokens,
                timeout_seconds=config.timeout_seconds,
            )
        elif args.max_output_tokens:
            config = DeepSeekConfig(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.model,
                reasoning_effort=config.reasoning_effort,
                max_output_tokens=args.max_output_tokens,
                timeout_seconds=config.timeout_seconds,
            )
        try:
            report = DeepSeekAnalyzer(config).analyze(context)
        except DeepSeekError as exc:
            print(f"DeepSeek analyzer failed ({exc.category})", file=sys.stderr)
            return 2
    else:
        report = FixtureAnalyzer().analyze(context)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(report, context), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
