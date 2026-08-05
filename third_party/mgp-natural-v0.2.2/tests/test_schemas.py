from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from mgp_natural.util.io import iter_jsonl


def _schema(name: str) -> dict:
    return json.loads((Path("schemas") / name).read_text(encoding="utf-8"))


def test_all_schemas_are_valid_draft_2020_12() -> None:
    for path in Path("schemas").glob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)


def test_blind_annotation_and_adjudication_fixtures_validate() -> None:
    schemas = {
        "blind_items.jsonl": _schema("blind_item.schema.json"),
        "annotations_valid.jsonl": _schema("annotation.schema.json"),
        "adjudications_valid.jsonl": _schema("adjudication.schema.json"),
        "predictions.jsonl": _schema("prediction.schema.json"),
        "trajectory.jsonl": _schema("trajectory.schema.json"),
    }
    for filename, schema in schemas.items():
        validator = jsonschema.Draft202012Validator(schema)
        for row in iter_jsonl(Path("data/fixtures") / filename):
            validator.validate(row)

