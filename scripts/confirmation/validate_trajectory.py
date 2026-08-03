#!/usr/bin/env python3
"""Validate prospective trajectory cases without evaluating model performance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--schema", type=Path, default=Path("confirmation/schemas/trajectory.schema.json")
    )
    args = parser.parse_args()
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    rows = [
        json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line
    ]
    errors = []
    for index, row in enumerate(rows):
        errors.extend(f"row {index}: {error.message}" for error in validator.iter_errors(row))
    if errors:
        raise SystemExit("trajectory validation failed:\n- " + "\n- ".join(errors))
    print(json.dumps({"status": "SCHEMA_VALID_ONLY", "trajectory_count": len(rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
