#!/usr/bin/env python3
"""Evaluate already labelled trajectory observations with cluster resampling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ask.eval.trajectory import TrajectoryStep, aggregate_trajectories, evaluate_trajectory

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "confirmation/schemas/trajectory_result.schema.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=43017)
    args = parser.parse_args()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    records = [
        json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line
    ]
    errors = []
    for index, record in enumerate(records):
        errors.extend(f"row {index}: {error.message}" for error in validator.iter_errors(record))
    if errors:
        raise SystemExit("trajectory input validation failed:\n- " + "\n- ".join(errors))
    results = [
        evaluate_trajectory(
            record["trajectory_id"], [TrajectoryStep(**step) for step in record["steps"]]
        )
        for record in records
    ]
    report = aggregate_trajectories(
        results, bootstrap_samples=args.bootstrap_samples, seed=args.seed
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "trajectory_count": len(results)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
