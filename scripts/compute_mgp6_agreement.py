#!/usr/bin/env python3
"""Compute M3-W12 advisor agreement for the 12-item MGP-6 subsample."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ksa.eval.mgp6_agreement import compute_agreement_csv  # noqa: E402

ADVISOR_TEMPLATE = Path("runs/m3w12/advisor_annotation_template_v1.jsonl")


def _selected_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                ids.add(json.loads(line)["scenario_id"])
    return ids


def _advisor_missing_message(path: Path) -> str:
    lines = [
        f"error: advisor annotation file not found: {path}",
        "",
        "M3-W12 requires an independently filled advisor annotation file.",
        f"Start from the template: {ADVISOR_TEMPLATE}",
        "Save the completed copy as: runs/m3w12/advisor_annotations_v1.jsonl",
        "Replace every TODO value before rerunning this command.",
    ]
    if ADVISOR_TEMPLATE.exists():
        lines.append("The template file exists in this checkout.")
    else:
        lines.append("The template file is not present in this Colab package.")
    return "\n".join(lines) + "\n"


def _require_file(parser: argparse.ArgumentParser, path: Path, label: str) -> None:
    if not path.exists():
        parser.exit(2, f"error: {label} file not found: {path}\n")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--student", type=Path, default=Path("data/mgp6_v1_seed0.jsonl"))
    p.add_argument("--advisor", type=Path, required=True)
    p.add_argument(
        "--subsample",
        type=Path,
        default=Path("data/mgp6_advisor_subsample_v1.jsonl"),
        help="Cold advisor package; used only to select the 12 scenario ids.",
    )
    p.add_argument("--out", type=Path, default=Path("runs/m3w12/agreement.csv"))
    args = p.parse_args()

    _require_file(p, args.student, "student gold")
    _require_file(p, args.subsample, "advisor subsample")
    if not args.advisor.exists():
        p.exit(2, _advisor_missing_message(args.advisor))
    if args.advisor.resolve() == ADVISOR_TEMPLATE.resolve():
        p.exit(
            2,
            "error: --advisor points to the blank template. "
            "Use a completed advisor annotation copy instead.\n",
        )

    try:
        rows = compute_agreement_csv(
            student_path=args.student,
            advisor_path=args.advisor,
            selected_ids=_selected_ids(args.subsample),
            out_path=args.out,
        )
    except ValueError as exc:
        p.exit(2, f"error: {exc}\n")
    agree = sum(1 for row in rows if row.agree)
    total = len(rows)
    print(f"wrote {args.out}")
    print(f"overall field agreement: {agree}/{total} = {agree / total:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
