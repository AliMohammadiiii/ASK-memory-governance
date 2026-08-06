from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def test_model_matrix_is_broad_but_not_authorized_or_executed() -> None:
    matrix = yaml.safe_load((ROOT / "configs/experiments/model_matrix.yaml").read_text())
    schema = json.loads((ROOT / "configs/experiments/model_matrix.schema.json").read_text())
    Draft202012Validator(schema).validate(matrix)
    assert {"Qwen", "Gemma", "Llama"} <= {row["family"] for row in matrix["systems"]}
    assert len({row["family"] for row in matrix["systems"]}) >= 4
    assert matrix["paid_inference_authorized"] is False
    assert {row["status"] for row in matrix["systems"]} == {"not_run"}
