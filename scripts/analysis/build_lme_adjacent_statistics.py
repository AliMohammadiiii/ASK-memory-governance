#!/usr/bin/env python3
"""Recompute the four predeclared adjacent LongMemEval comparisons."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs_local/lme_final_controller_v12_qwen_180"
OUTPUT = ROOT / "artifacts/analysis/lme_v12_adjacent_mcnemar.json"
ORDER = ("b1", "b3", "b2", "b4", "controller")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(name: str) -> dict[str, bool]:
    path = RUN / name / "judgments.jsonl"
    return {
        row["session_id"]: bool(row["correct"])
        for row in (json.loads(line) for line in path.read_text().splitlines() if line)
    }


def _exact(b: int, c: int) -> float:
    n = b + c
    return min(1.0, 2 * sum(math.comb(n, index) for index in range(min(b, c) + 1)) / 2**n)


def _holm(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    adjusted = [0.0] * len(values)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (len(values) - rank) * values[index]))
        adjusted[index] = running
    return adjusted


def build() -> dict[str, Any]:
    correctness = {name: _rows(name) for name in ORDER}
    comparisons = []
    for better, lower in zip(ORDER[1:], ORDER[:-1], strict=True):
        ids = sorted(correctness[better].keys() & correctness[lower].keys())
        b = sum(correctness[better][item] and not correctness[lower][item] for item in ids)
        c = sum(correctness[lower][item] and not correctness[better][item] for item in ids)
        comparisons.append(
            {
                "better": better,
                "lower": lower,
                "paired_n": len(ids),
                "b": b,
                "c": c,
                "risk_difference": (b - c) / len(ids),
                "raw_exact_two_sided_p": _exact(b, c),
            }
        )
    adjusted = _holm([row["raw_exact_two_sided_p"] for row in comparisons])
    for row, value in zip(comparisons, adjusted, strict=True):
        row["holm_adjusted_p"] = value
    return {
        "schema_version": "1.0",
        "status": "VERIFIED_ADDITIVE_CORRECTION",
        "family_definition": "four predeclared adjacent comparisons in B1<B3<B2<B4<ASK order",
        "family_size": 4,
        "source_sha256": {name: _sha256(RUN / name / "judgments.jsonl") for name in ORDER},
        "comparisons": comparisons,
    }


def main() -> int:
    report = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "family_size": report["family_size"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
