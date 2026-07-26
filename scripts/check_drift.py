"""Compare archived vs. current report.json files for evaluator drift.

M1-W4 §3.4 acceptance: per-competency accuracy across (W2-archived ↔ W4-rerun)
and (W3-archived ↔ W4-rerun) must agree within ±1pp. Larger drift means the
evaluator was modified between weeks and earlier numbers are no longer
comparable; the run must be flagged in NOTES/m1w4_evaluator_drift.md.

Usage:
    python scripts/check_drift.py \
        --archived runs/m1w2/no_memory/report.json runs/m1w4/no_memory/report.json \
        --archived runs/m1w3/flat_vector/report.json runs/m1w4/flat_vector/report.json \
        > NOTES/m1w4_evaluator_drift.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_TOLERANCE_PP = 1.0


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _row_index(report: dict) -> dict[str, dict]:
    return {r["competency"]: r for r in report.get("rows", [])}


def _check_pair(archived: Path, current: Path) -> tuple[str, list[str], bool]:
    a = _load(archived)
    c = _load(current)
    name = a.get("baseline_name", archived.stem)
    a_rows = _row_index(a)
    c_rows = _row_index(c)

    out: list[str] = []
    out.append(f"### `{name}`: archived `{archived}` ↔ current `{current}`")
    out.append("")
    out.append("| Competency | Archived acc | Current acc | Δ (pp) | Within ±1pp? |")
    out.append("|---|---:|---:|---:|:-:|")

    any_drift = False
    for comp in sorted(set(a_rows) | set(c_rows)):
        a_r = a_rows.get(comp)
        c_r = c_rows.get(comp)
        a_pct = (a_r["accuracy"] * 100) if a_r else None
        c_pct = (c_r["accuracy"] * 100) if c_r else None
        if a_pct is None or c_pct is None:
            out.append(
                f"| {comp} | "
                f"{'—' if a_pct is None else f'{a_pct:.1f}%'} | "
                f"{'—' if c_pct is None else f'{c_pct:.1f}%'} | — | ✗ (missing) |"
            )
            any_drift = True
            continue
        delta = c_pct - a_pct
        ok = abs(delta) <= _TOLERANCE_PP
        if not ok:
            any_drift = True
        out.append(
            f"| {comp} | {a_pct:.1f}% | {c_pct:.1f}% | {delta:+.1f} | {'✓' if ok else '✗'} |"
        )

    a_overall = a.get("overall_accuracy", 0.0) * 100
    c_overall = c.get("overall_accuracy", 0.0) * 100
    overall_delta = c_overall - a_overall
    overall_ok = abs(overall_delta) <= _TOLERANCE_PP
    if not overall_ok:
        any_drift = True
    out.append(
        f"| **overall** | **{a_overall:.1f}%** | **{c_overall:.1f}%** | "
        f"**{overall_delta:+.1f}** | **{'✓' if overall_ok else '✗'}** |"
    )
    out.append("")
    return name, out, any_drift


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--archived",
        nargs=2,
        action="append",
        required=True,
        type=Path,
        metavar=("ARCHIVED.json", "CURRENT.json"),
        help="A pair of (archived, current) report.json paths. Repeat for multiple baselines.",
    )
    p.add_argument(
        "--tolerance-pp",
        type=float,
        default=_TOLERANCE_PP,
        help="Drift tolerance in percentage points; default 1.0.",
    )
    args = p.parse_args()

    print("# M1-W4 evaluator-drift report")
    print()
    print(f"Tolerance: ±{args.tolerance_pp:.1f} pp on per-competency accuracy.")
    print()
    print(
        "§3.4 acceptance: re-runs of W2 and W3 baselines drift from "
        "the archived numbers by less than ±1pp. Larger drift means the "
        "evaluator was modified between weeks and earlier numbers are no "
        "longer comparable. Document the offending row(s) below; the "
        "Gate G1 decision must reflect this."
    )
    print()

    any_overall_drift = False
    for archived, current in args.archived:
        try:
            _, lines, drift = _check_pair(archived, current)
        except FileNotFoundError as e:
            print(f"### `{archived}` → `{current}`: **MISSING** ({e})")
            print()
            any_overall_drift = True
            continue
        for line in lines:
            print(line)
        if drift:
            any_overall_drift = True

    print("---")
    if any_overall_drift:
        print()
        print(
            "**Verdict: drift detected** — at least one row exceeds the "
            "±1pp tolerance. The G1 gate decision must record this and "
            "either (a) explain the drift (a fix to the evaluator), or "
            "(b) re-run the prior weeks before merging the table."
        )
        return 2
    print()
    print(
        "**Verdict: no drift** — all per-competency accuracies match "
        "their archived counterparts within ±1pp. Cross-week comparisons "
        "in NOTES/m1w4_results.md are valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
