#!/usr/bin/env python3
"""Validate the prospective model matrix without executing inference."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    matrix = yaml.safe_load((ROOT / "configs/experiments/model_matrix.yaml").read_text())
    schema = json.loads((ROOT / "configs/experiments/model_matrix.schema.json").read_text())
    Draft202012Validator(schema).validate(matrix)
    families = {row["family"] for row in matrix["systems"]}
    required = {"Qwen", "Gemma", "Llama"}
    if not required <= families or len(families) < 4:
        raise SystemExit("matrix requires Qwen, Gemma, Llama, and one additional family")
    if matrix["paid_inference_authorized"] is not False:
        raise SystemExit("repository matrix must not imply paid authorization")
    if any(row["status"] == "completed" for row in matrix["systems"]):
        raise SystemExit("prospective matrix cannot mark an unverified run completed")
    print(
        json.dumps(
            {
                "status": "PASS_DRY_CONFIGURATION",
                "families": sorted(families),
                "systems": len(matrix["systems"]),
                "execution_authorized": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
