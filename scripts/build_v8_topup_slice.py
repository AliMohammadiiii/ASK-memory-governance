#!/usr/bin/env python3
"""Build the v8 TOP-UP slice: the strat30 questions NOT already answered
under v8 in the failure-replay run.

The v8 failure replay (runs/lme_m_modal_qwen35_9b_v8_v7_failures_nothink)
already produced v8 answers for the 70 v7-failure sessions. The homogeneous
full-180 estimate therefore only needs fresh v8 answers for the remaining
110 sessions. This script derives that set from the replay run itself (no
hand-maintained id lists) and writes a filtered slice.

    python scripts/build_v8_topup_slice.py \
        --slice data/slices/longmemeval_m_strat30_seed0.jsonl \
        --replay-run runs/lme_m_modal_qwen35_9b_v8_v7_failures_nothink/controller \
        --out data/slices/longmemeval_m_strat30_seed0_v8_topup110.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice", type=Path, required=True)
    parser.add_argument("--replay-run", type=Path, required=True,
                        help="replay system dir containing judgments.jsonl")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    replay_ids = {r["session_id"]
                  for r in jsonl(args.replay_run / "judgments.jsonl")}
    slice_rows = list(jsonl(args.slice))
    slice_ids = {r["session_id"] for r in slice_rows}

    stray = replay_ids - slice_ids
    if stray:
        raise SystemExit(f"replay contains ids not in slice: {sorted(stray)[:5]}")

    remaining = [r for r in slice_rows if r["session_id"] not in replay_ids]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for r in remaining:
            handle.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"slice total     : {len(slice_rows)}")
    print(f"already v8 (replay): {len(replay_ids)}")
    print(f"top-up remaining: {len(remaining)} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
