#!/usr/bin/env python3
"""Tiny offline execution smoke for the canonical MGP-6 v2 policy harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from systems.policies import SYSTEMS


def _load_prefix(path: Path, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
            if len(rows) >= limit:
                break
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "mgp6_v2.jsonl",
    )
    parser.add_argument("--system", choices=sorted(SYSTEMS), default="b1")
    parser.add_argument("--limit", type=int, default=2)
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be positive")
    scenarios = _load_prefix(args.input, args.limit)
    if len(scenarios) != args.limit:
        raise SystemExit(f"expected {args.limit} scenarios, found {len(scenarios)}")

    predict = SYSTEMS[args.system]
    required = {
        "predicted_action",
        "predicted_memory_state",
        "predicted_answer",
        "confidence",
    }
    for scenario in scenarios:
        prediction = predict(scenario)
        missing = required - prediction.keys()
        if missing:
            raise SystemExit(
                f"{scenario.get('scenario_id')}: missing prediction fields {sorted(missing)}"
            )
        if prediction["predicted_action"] not in {
            "KEEP",
            "SUPERSEDE",
            "ABSTAIN",
        }:
            raise SystemExit(
                f"{scenario.get('scenario_id')}: invalid action {prediction['predicted_action']!r}"
            )
    print(f"MGP-6 v2 smoke passed: system={args.system} scenarios={len(scenarios)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
