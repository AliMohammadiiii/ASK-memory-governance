#!/usr/bin/env python3
"""Validate prospective MGP-Natural annotations and optional adjudications."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ask.confirmation.mgpn_validation import (
    validate_adjudication_set,
    validate_annotation_set,
)

ROOT = Path(__file__).resolve().parents[2]


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    return value


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise SystemExit(f"{path}:{line_number}: expected a JSON object")
        rows.append(value)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--adjudications", type=Path)
    parser.add_argument("--minimum-annotators", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    packet = _jsonl(args.packet)
    annotations = _jsonl(args.annotations)
    annotation_result = validate_annotation_set(
        packet,
        annotations,
        _json(ROOT / "confirmation/schemas/annotation.schema.json"),
        minimum_annotators=args.minimum_annotators,
    )
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "annotation": annotation_result,
        "adjudication": None,
    }
    if args.adjudications:
        result["adjudication"] = validate_adjudication_set(
            annotations,
            _jsonl(args.adjudications),
            _json(ROOT / "confirmation/schemas/adjudication.schema.json"),
        )
    valid = annotation_result["status"] == "VALID" and (
        result["adjudication"] is None or result["adjudication"]["status"] == "VALID"
    )
    result["status"] = "VALID" if valid else "INVALID"
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
