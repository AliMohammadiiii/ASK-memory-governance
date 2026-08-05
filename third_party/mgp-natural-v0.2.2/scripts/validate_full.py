from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema

from mgp_natural.blinding.packet import verify_packet
from mgp_natural.ontology.contract import validate_construction_item
from mgp_natural.util.io import iter_jsonl, read_json, write_json


def _validate_jsonl(path: Path, schema: dict[str, Any]) -> int:
    validator = jsonschema.Draft202012Validator(schema)
    count = 0
    for row_number, row in enumerate(iter_jsonl(path), 1):
        errors = sorted(validator.iter_errors(row), key=lambda error: list(error.path))
        if errors:
            raise ValueError(f"{path}:{row_number}: {errors[0].message}")
        count += 1
    return count


def validate(repo_root: Path) -> dict[str, Any]:
    private = repo_root / ".private" / "full"
    required = [
        repo_root / "reports" / "INPUT_INVENTORY_FULL.json",
        repo_root / "reports" / "SOURCE_INTEGRITY.json",
        repo_root / "reports" / "STUDYCHAT_FULL_RECONSTRUCTION.json",
        repo_root / "reports" / "WIKICONV_2003_RECONSTRUCTION.json",
        repo_root / "reports" / "WIKICONV_2018_RECONSTRUCTION.json",
        repo_root / "reports" / "PII_SCAN_FULL.json",
        repo_root / "reports" / "AI_ANNOTATION_AGREEMENT.json",
        repo_root / "reports" / "SPLIT_AUDIT_FULL.json",
        private / "construction_items_redacted.jsonl",
        private / "packets" / "mgp_natural_full_annotation.zip",
    ]
    missing = [path.relative_to(repo_root).as_posix() for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"full validation missing artifacts: {missing}")
    source_integrity = read_json(repo_root / "reports" / "SOURCE_INTEGRITY.json")
    if source_integrity.get("status") != "PASS":
        raise ValueError("source integrity is not PASS")
    construction_count = 0
    for row in iter_jsonl(private / "construction_items_redacted.jsonl"):
        validate_construction_item(row)
        construction_count += 1
    if construction_count == 0:
        raise ValueError("full validation found no construction candidates")
    ai_schema = read_json(repo_root / "schemas" / "ai_annotation.schema.json")
    ai_counts = {}
    for index in range(1, 4):
        path = (
            repo_root
            / "data"
            / "derived"
            / "ai_provisional"
            / f"annotations.pass{index:02d}.ai_provisional.jsonl"
        )
        ai_counts[f"pass{index:02d}"] = _validate_jsonl(path, ai_schema)
    if len(set(ai_counts.values())) != 1:
        raise ValueError("AI provisional passes do not have identical coverage")
    packet = verify_packet(private / "packets" / "mgp_natural_full_annotation.zip")
    gold_paths = [
        path
        for path in (repo_root / ".private").rglob("*gold*.jsonl")
        if path.is_file()
    ]
    if gold_paths:
        raise ValueError("human-gold path must remain empty before authorized adjudication")
    report = {
        "schema_version": "2.0",
        "status": "PASS_MACHINE_VALIDATION_HUMAN_GATES_PENDING",
        "construction_items": construction_count,
        "ai_pass_counts": ai_counts,
        "private_packet": packet,
        "human_gold_items": 0,
        "publication_eligible": False,
    }
    write_json(repo_root / "reports" / "FULL_VALIDATION.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate full-source private artifacts")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(json.dumps(validate(args.repo_root.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()

