"""Build a LongMemEval slice containing only failed sessions from a run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ask.data.longmemeval import iter_longmemeval_s  # noqa: E402


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _judgments_path(run: Path) -> Path:
    if run.is_file():
        return run
    candidates = [
        run / "judgments.jsonl",
        run / "controller" / "judgments.jsonl",
        run / "runs" / "m4w13_50_t4_quality" / "controller" / "judgments.jsonl",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"could not find judgments.jsonl under {run}")


def build_failed_slice(
    *,
    source_slice: Path,
    run: Path,
    out: Path,
    ids_out: Path | None = None,
) -> dict[str, Any]:
    judgments_path = _judgments_path(run)
    judgments = _load_jsonl(judgments_path)
    if not judgments:
        raise ValueError(
            f"no judgments found in {judgments_path}; cannot build a failed slice"
        )
    failed_ids = [
        str(row["session_id"])
        for row in judgments
        if row.get("correct") is False
    ]
    judged_ids = {
        str(row.get("session_id"))
        for row in judgments
        if row.get("session_id") is not None
    }
    failed_set = set(failed_ids)

    slice_session_ids: set[str] = set()
    sessions = []
    for session in iter_longmemeval_s(source_slice):
        slice_session_ids.add(session.session_id)
        if session.session_id in failed_set:
            sessions.append(session)

    # Fail loudly when the slice and the run's judgments describe disjoint
    # session sets — almost always a wrong --slice/--run pairing. Writing an
    # empty (or mismatched) slice silently is the dangerous behavior we guard.
    if judged_ids and slice_session_ids and judged_ids.isdisjoint(slice_session_ids):
        raise ValueError(
            f"source slice {source_slice} and run judgments {judgments_path} "
            f"share no session IDs ({len(slice_session_ids)} slice ids vs "
            f"{len(judged_ids)} judged ids); refusing to build from a mismatched "
            "run. Check the --slice/--run pairing."
        )

    found = {session.session_id for session in sessions}
    missing = [sid for sid in failed_ids if sid not in found]

    if failed_ids and not sessions:
        raise ValueError(
            f"{len(failed_ids)} failed session(s) in {judgments_path} but none are "
            f"present in source slice {source_slice}; refusing to write an empty "
            "failed slice (check the --slice/--run pairing)."
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for session in sessions:
            fh.write(json.dumps(session.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")

    if ids_out is not None:
        ids_out.parent.mkdir(parents=True, exist_ok=True)
        ids_out.write_text("\n".join(session.session_id for session in sessions) + "\n", encoding="utf-8")

    return {
        "source_slice": str(source_slice),
        "judgments": str(judgments_path),
        "out": str(out),
        "n_judgments": len(judgments),
        "n_judged_sessions": len(judged_ids),
        "n_slice_sessions": len(slice_session_ids),
        "n_failed": len(failed_ids),
        "n_written": len(sessions),
        "failed_session_ids": [session.session_id for session in sessions],
        "missing_session_ids": missing,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice", required=True, type=Path, help="Original LongMemEval slice.")
    parser.add_argument(
        "--run",
        required=True,
        type=Path,
        help="Run directory, controller directory, or judgments.jsonl path.",
    )
    parser.add_argument("--out", required=True, type=Path, help="Output failed-only JSONL slice.")
    parser.add_argument("--ids-out", type=Path, help="Optional newline-delimited session id file.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    summary = build_failed_slice(
        source_slice=args.slice,
        run=args.run,
        out=args.out,
        ids_out=args.ids_out,
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            f"wrote {summary['n_written']}/{summary['n_failed']} failed sessions "
            f"from {summary['judgments']} -> {summary['out']}"
        )
        if summary["missing_session_ids"]:
            print(f"missing ids: {', '.join(summary['missing_session_ids'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
