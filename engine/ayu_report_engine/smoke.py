"""One-request DeepSeek Responses API smoke test.

This module is intentionally opt-in. Importing it or running ordinary tests
never reads a key or makes a network request.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .benchmark import run_live_smoke
from .deepseek import DeepSeekConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explicit one-request DeepSeek smoke test")
    parser.add_argument("--live", action="store_true", help="required acknowledgement for network calls")
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=Path(__file__).parents[1] / "tests" / "fixtures",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parents[1] / ".benchmark" / "smoke.json",
    )
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("pass --live to make a network request")
    result = run_live_smoke(args.fixtures, DeepSeekConfig.from_env(load_local_files=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result.get("status"), "output": str(args.output)}))
    return 0 if result.get("status") == "success" else 2


if __name__ == "__main__":
    sys.exit(main())
