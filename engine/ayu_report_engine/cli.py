"""Small offline CLI used by local tests and future Actions."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .adapters.fit import context_from_fit_bytes
from .adapters.running_page import load_running_page_context
from .analysis import FixtureAnalyzer
from .render import render_html


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render an offline Ayu Running report")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--sqlite", type=Path)
    parser.add_argument("--fit", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.fit:
        context = context_from_fit_bytes(args.fit.read_bytes(), source_ref=args.fit.name)
    elif args.json:
        context = load_running_page_context(args.json, args.sqlite, args.run_id)
    else:
        raise SystemExit("one of --json or --fit is required")
    report = FixtureAnalyzer().analyze(context)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(report, context), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
