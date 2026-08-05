from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from mgp_natural.ontology.contract import validate_construction_item
from mgp_natural.util.io import iter_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate construction candidates structurally and semantically"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    args = parser.parse_args()
    validator = Draft202012Validator(json.loads(args.schema.read_text(encoding="utf-8")))
    count = 0
    for row in iter_jsonl(args.input):
        validator.validate(row)
        validate_construction_item(row)
        count += 1
    print(json.dumps({"status": "VALID", "items": count}, sort_keys=True))


if __name__ == "__main__":
    main()

