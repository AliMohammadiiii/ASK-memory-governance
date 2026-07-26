#!/usr/bin/env python3
"""Build a competency-stratified LongMemEval slice (N per competency).

The colab/modal runner evaluates a CONTIGUOUS index range of a slice file, so
to evaluate "N of each competency" we first materialize a slice whose rows are
exactly N per competency (deterministic under --seed), then run it as the range
0..(rows-1).

Usage:
    python scripts/build_stratified_slice.py \
        --src data/slices/longmemeval_m_full.jsonl \
        --out data/slices/longmemeval_m_strat30_seed0.jsonl \
        --per-competency 30 --seed 0

Determinism: competencies are processed in a fixed order; within each, the row
indices are shuffled by a seeded RNG and the first N are kept. Rows are written
in ascending original-index order so shard assignment is stable across rebuilds.
The full corpus_sessions (the retrieval haystack) are preserved unchanged — only
the SET of question rows is subsetted, so the benchmark itself is untouched.
"""

from __future__ import annotations

import argparse
import random
import re
from collections import defaultdict
from pathlib import Path

# Grab the top-level competency without json.loads of the (multi-MB) full row.
_COMPETENCY_RE = re.compile(r'"competency"\s*:\s*"([^"]+)"')

# Canonical processing order (stable, so the seeded selection is reproducible).
_COMPETENCY_ORDER = [
    "single-session-user",
    "single-session-assistant",
    "single-session-preference",
    "multi-session",
    "knowledge-update",
    "temporal-reasoning",
]


def _competency_of(line: str) -> str | None:
    m = _COMPETENCY_RE.search(line)
    return m.group(1) if m else None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--src", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--per-competency", type=int, default=30)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    if not args.src.exists():
        raise SystemExit(f"missing source slice: {args.src}")

    # Pass 1: index -> competency (cheap regex, no full parse).
    by_comp: dict[str, list[int]] = defaultdict(list)
    with args.src.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            comp = _competency_of(line)
            if comp is not None:
                by_comp[comp].append(i)

    # Deterministic selection: seeded shuffle per competency, first N.
    selected: set[int] = set()
    summary: list[tuple[str, int, int]] = []
    comps = _COMPETENCY_ORDER + sorted(c for c in by_comp if c not in _COMPETENCY_ORDER)
    for comp in comps:
        idxs = by_comp.get(comp)
        if not idxs:
            continue
        rng = random.Random(f"{args.seed}:{comp}")
        shuffled = list(idxs)
        rng.shuffle(shuffled)
        take = shuffled[: args.per_competency]
        selected.update(take)
        summary.append((comp, len(idxs), len(take)))

    # Pass 2: write the selected rows in ascending original-index order.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with args.src.open("r", encoding="utf-8") as fin, args.out.open("w", encoding="utf-8") as fout:
        for i, line in enumerate(fin):
            if i in selected:
                if not line.endswith("\n"):
                    line += "\n"
                fout.write(line)
                written += 1

    print(f"[stratified] wrote {written} rows -> {args.out}")
    for comp, avail, took in summary:
        flag = "" if took == args.per_competency else f"  (only {avail} available)"
        print(f"[stratified]   {comp}: {took}/{avail}{flag}")
    short = [c for c, avail, took in summary if took < args.per_competency]
    if short:
        print(f"[stratified] NOTE: {short} had fewer than {args.per_competency} rows; took all.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
