"""Per-competency win / loss / tie matrix between two baseline runs (M1-W3 §3.4).

The merged accuracy table answers "did X improve over Y on average?" but
masks per-session signal. A 50-session slice that's 50% on both baselines
might be 50 wins traded for 50 losses or all-correct on the same 25.
The win/loss/tie matrix exposes that.

Inputs: two `judgments.jsonl` files (the run-level grade-per-session
records the evaluator persists as the run progresses). Outputs: a
markdown table per competency with counts of {ref-only-correct,
new-only-correct, both-correct, both-wrong} plus the lists of session
IDs in each cell so §3.5 sanity-checking can read 5 wins / 5 losses
directly.

Usage:

    python scripts/win_loss.py \
        --ref runs/m1w2/no_memory/judgments.jsonl \
        --new runs/m1w3/flat_vector/judgments.jsonl \
        > NOTES/m1w3_win_loss.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Cell:
    ref_correct: bool
    new_correct: bool

    @property
    def label(self) -> str:
        if self.ref_correct and self.new_correct:
            return "both-correct"
        if self.ref_correct and not self.new_correct:
            return "ref-only"  # regression
        if not self.ref_correct and self.new_correct:
            return "new-only"  # improvement
        return "both-wrong"


def _load_judgments(path: Path) -> dict[str, dict]:
    """`{session_id: judgment_record}` from a judgments.jsonl file."""
    out: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out[rec["session_id"]] = rec
    return out


def _build_matrix(
    ref: dict[str, dict], new: dict[str, dict]
) -> dict[str, dict[Cell, list[str]]]:
    """`{competency: {Cell: [session_id, ...]}}`. Sessions absent from one
    side are dropped — both runs must have evaluated the same set."""
    matrix: dict[str, dict[Cell, list[str]]] = defaultdict(lambda: defaultdict(list))
    common = set(ref.keys()) & set(new.keys())
    for sid in sorted(common):
        r = ref[sid]
        n = new[sid]
        comp = r.get("competency") or n.get("competency") or "unknown"
        cell = Cell(ref_correct=bool(r["correct"]), new_correct=bool(n["correct"]))
        matrix[comp][cell].append(sid)
    return matrix


def _render_md(
    matrix: dict[str, dict[Cell, list[str]]],
    ref_path: Path,
    new_path: Path,
    ref_name: str = "ref",
    new_name: str = "new",
) -> str:
    lines: list[str] = []
    lines.append(f"# Win / loss / tie — `{new_name}` vs. `{ref_name}`\n")
    lines.append(f"- **Reference judgments:** `{ref_path}`")
    lines.append(f"- **New judgments:** `{new_path}`")
    lines.append("")
    lines.append(
        "Per-competency cell counts. **new-only** = `new` improved over "
        "`ref`; **ref-only** = `new` regressed; **both-correct** / "
        "**both-wrong** = agreement. The `new-only` and `ref-only` cells "
        "are exactly the disagreement set the §3.5 sanity check spot-checks."
    )
    lines.append("")
    header = ["Competency", "n", "both-correct", "new-only (gain)",
              "ref-only (loss)", "both-wrong"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|---|---:|---:|---:|---:|---:|")

    overall = defaultdict(int)
    for comp in sorted(matrix):
        cells = matrix[comp]
        n_total = sum(len(v) for v in cells.values())
        bc = len(cells.get(Cell(True, True), []))
        no = len(cells.get(Cell(False, True), []))
        ro = len(cells.get(Cell(True, False), []))
        bw = len(cells.get(Cell(False, False), []))
        lines.append(f"| {comp} | {n_total} | {bc} | {no} | {ro} | {bw} |")
        overall["n"] += n_total
        overall["bc"] += bc
        overall["no"] += no
        overall["ro"] += ro
        overall["bw"] += bw
    lines.append(
        f"| **all** | {overall['n']} | {overall['bc']} | "
        f"{overall['no']} | {overall['ro']} | {overall['bw']} |"
    )
    lines.append("")
    lines.append(
        f"Net = (new-only) − (ref-only) = "
        f"{overall['no'] - overall['ro']} sessions across all competencies."
    )

    # Disagreement session lists for the §3.5 spot-check.
    lines.append("\n## Disagreement session ids (read these in `judgments.jsonl`)\n")
    for comp in sorted(matrix):
        cells = matrix[comp]
        no_ids = cells.get(Cell(False, True), [])
        ro_ids = cells.get(Cell(True, False), [])
        if not no_ids and not ro_ids:
            continue
        lines.append(f"### {comp}\n")
        lines.append(f"- new-only (gain): {no_ids or '—'}")
        lines.append(f"- ref-only (loss): {ro_ids or '—'}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ref", required=True, type=Path,
                   help="Reference judgments.jsonl (e.g. M1-W2 no_memory)")
    p.add_argument("--new", required=True, type=Path,
                   help="New judgments.jsonl (e.g. M1-W3 flat_vector)")
    p.add_argument("--ref-name", default="ref", type=str)
    p.add_argument("--new-name", default="new", type=str)
    args = p.parse_args()

    ref = _load_judgments(args.ref)
    new = _load_judgments(args.new)
    matrix = _build_matrix(ref, new)
    sys.stdout.write(_render_md(
        matrix, args.ref, args.new,
        ref_name=args.ref_name, new_name=args.new_name,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
