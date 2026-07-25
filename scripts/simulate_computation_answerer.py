"""Replay the computation answerer without LLM or judge calls."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ask.eval.computation_replay import (  # noqa: E402
    simulate_computation_on_answers,
    simulate_computation_on_slice,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slice",
        required=True,
        type=Path,
        help="LongMemEval JSONL slice.",
    )
    parser.add_argument(
        "--answers",
        type=Path,
        help="Existing answers.jsonl; required for --mode prompt.",
    )
    parser.add_argument(
        "--mode",
        choices=("supporting", "haystack", "prompt"),
        default="supporting",
        help="Evidence source. prompt parses retrieved memory from --answers.",
    )
    parser.add_argument("--session-id", help="Only replay one session.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.mode == "prompt":
        if args.answers is None:
            raise SystemExit("--answers is required with --mode prompt")
        rows = simulate_computation_on_answers(
            args.slice,
            args.answers,
            session_id=args.session_id,
        )
    else:
        rows = simulate_computation_on_slice(
            args.slice,
            mode=args.mode,
            session_id=args.session_id,
        )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_table(rows)
    return 0


def _print_table(rows: list[dict[str, object]]) -> None:
    headers = ("session_id", "competency", "intent", "safe", "computed_answer", "gold_answer")
    print(" | ".join(headers))
    print(" | ".join("---" for _ in headers))
    for row in rows:
        print(
            " | ".join(
                [
                    str(row.get("session_id") or ""),
                    str(row.get("competency") or ""),
                    str(row.get("intent") or ""),
                    "yes" if row.get("safe_to_bypass") else "no",
                    _compact(str(row.get("computed_answer") or "")),
                    _compact(str(row.get("gold_answer") or "")),
                ]
            )
        )


def _compact(text: str, *, limit: int = 72) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


if __name__ == "__main__":
    raise SystemExit(main())
