from __future__ import annotations

import argparse
import json
from pathlib import Path

from mgp_natural.audits.execution import render_execution_summary, write_execution_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate consolidated execution summary")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    report = write_execution_summary(args.root, args.output)
    if args.markdown is not None:
        args.markdown.write_text(render_execution_summary(report), encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

