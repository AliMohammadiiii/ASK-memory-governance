#!/usr/bin/env python3
"""Compare two relation-classifier prediction files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ksa.classifier.metrics import per_label_metrics  # noqa: E402


def _read(path: Path) -> tuple[list[str], list[str]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return (
        [r["gold_relation"] for r in rows],
        [r["prediction"]["relation_to_prior_state"] for r in rows],
    )


def _f1_for(label: str, gold: list[str], pred: list[str]) -> float | None:
    for row in per_label_metrics(gold, pred):
        if row.label == label:
            return row.f1
    raise AssertionError(label)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, type=Path)
    p.add_argument("--jitter", required=True, type=Path)
    args = p.parse_args()

    gold0, pred0 = _read(args.base)
    gold1, pred1 = _read(args.jitter)
    if gold0 != gold1:
        raise SystemExit("gold labels differ between prediction files")
    base = _f1_for("contradict", gold0, pred0)
    jitter = _f1_for("contradict", gold1, pred1)
    payload = {
        "contradict_f1_t0": base,
        "contradict_f1_t03": jitter,
        "delta": None if base is None or jitter is None else jitter - base,
        "identical_predictions": pred0 == pred1,
        "n": len(gold0),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
