"""Build a LongMemEval slice (any size) from a release file.

The same builder produces the 50-session dev slice (M1-W1 §3.1) and the full
500-question thesis set (M4-W13). Works on LongMemEval-S or -M, in JSONL or
JSON-array form.

Usage:
    # 50-question stratified dev slice (seed 0)
    python scripts/build_slice.py \
        --in  data/longmemeval_s.json \
        --out data/slices/longmemeval_s_50_seed0.jsonl \
        --n   50 --seed 0

    # Full 500-question set (no sampling; deterministic id order)
    python scripts/build_slice.py \
        --in  data/longmemeval_s.json \
        --out data/slices/longmemeval_s_full.jsonl \
        --n   all

    # LongMemEval-M full set (converts the big array to streaming JSONL)
    python scripts/build_slice.py \
        --in  data/longmemeval_m.json \
        --out data/slices/longmemeval_m_full.jsonl \
        --n   all

The input file is a LongMemEval release; researchers must place it locally —
not redistributable.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Allow `python scripts/build_slice.py` from repo root without `pip install`.
_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ksa.data.longmemeval import (  # noqa: E402  (sys.path insert above)
    iter_longmemeval_s,
    sample_slice,
    write_slice_jsonl,
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", required=True, type=Path)
    p.add_argument(
        "--out", dest="dst", required=True, type=Path,
        help="Output JSONL; default convention: data/slices/longmemeval_s_<n>_seed<seed>.jsonl",
    )
    p.add_argument("--n", default="50",
                   help="Slice size, or 'all'/'full'/0 for the entire release "
                        "(no sampling). Default 50.")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    if not args.src.exists():
        print(f"ERROR: input not found: {args.src}", file=sys.stderr)
        return 2

    want_full = str(args.n).strip().lower() in {"all", "full", "0", "-1"}
    if not want_full:
        try:
            n = int(args.n)
        except ValueError:
            print(f"ERROR: --n must be an integer or 'all'; got {args.n!r}",
                  file=sys.stderr)
            return 2
    else:
        n = -1  # resolved to the full pool size after loading

    sessions = list(iter_longmemeval_s(args.src))
    print(f"Loaded {len(sessions)} sessions from {args.src}")

    if want_full or n >= len(sessions):
        # Whole release, deterministically ordered — no stratified sampling.
        sliced = sample_slice(sessions, n=len(sessions), seed=args.seed)
    else:
        sliced = sample_slice(sessions, n=n, seed=args.seed, stratify_by="competency")
    write_slice_jsonl(sliced, args.dst)

    counts = Counter(s.competency for s in sliced)
    print(f"Wrote {len(sliced)} sessions to {args.dst}")
    print("Competency distribution:")
    for k in sorted(counts):
        print(f"  {k:30s} {counts[k]}")
    print(json.dumps({"out": str(args.dst), "n": len(sliced), "seed": args.seed}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
