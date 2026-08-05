"""Prospective semantic validation of immutable annotations."""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from mgp_natural.blinding.packet import scan_prohibited_keys
from mgp_natural.errors import ValidationError
from mgp_natural.ontology.contract import Action, canonical_value
from mgp_natural.util.io import canonical_json_bytes, iter_jsonl, write_json

ANNOTATION_PROTOCOL_VERSION = "1.0-prospective"
ANNOTATOR_MANUAL_VERSION = "1.0-prospective"


def row_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(row)).hexdigest()


def validate_annotation_row(row: dict[str, Any], item: dict[str, Any]) -> None:
    if row.get("protocol_version") != ANNOTATION_PROTOCOL_VERSION:
        raise ValidationError("annotation protocol version mismatch")
    if row.get("manual_version") != ANNOTATOR_MANUAL_VERSION:
        raise ValidationError("annotator manual version mismatch")
    if row.get("blind_id") != item.get("blind_id"):
        raise ValidationError("annotation references unknown blind_id")
    pseudonym = row.get("annotator_pseudonym")
    if not isinstance(pseudonym, str) or not pseudonym.strip():
        raise ValidationError("annotator pseudonym is required")
    excluded = row.get("exclude") is True
    action = row.get("action")
    if excluded and action is not None:
        raise ValidationError("row cannot be labeled and excluded")
    if not excluded and action is None:
        raise ValidationError("non-excluded row requires action")
    if excluded:
        if not isinstance(row.get("exclusion_reason"), str) or not row["exclusion_reason"].strip():
            raise ValidationError("excluded row requires exclusion reason")
        return
    if not isinstance(action, str):
        raise ValidationError("invalid action")
    try:
        parsed = Action(action)
    except (TypeError, ValueError) as exc:
        raise ValidationError("invalid action") from exc
    confidence = row.get("confidence")
    if not isinstance(confidence, int) or isinstance(confidence, bool) or not 1 <= confidence <= 5:
        raise ValidationError("confidence must be integer 1 through 5")
    evidence = row.get("evidence_turn_ids")
    turn_ids = {turn["turn_id"] for turn in item["dialogue"]}
    if not isinstance(evidence, list) or not evidence:
        raise ValidationError("evidence is required")
    if any(turn_id not in turn_ids for turn_id in evidence):
        raise ValidationError("annotation contains invalid evidence ID")
    if item["candidate_turn_id"] not in evidence:
        raise ValidationError("candidate turn must be evidence")
    rationale = row.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValidationError("rationale is required")
    result = row.get("resulting_value")
    prior = item["prior_value"]
    if parsed is Action.SUPERSEDE:
        if not isinstance(result, str) or not result.strip():
            raise ValidationError("SUPERSEDE requires resulting value")
        if canonical_value(result) == canonical_value(prior):
            raise ValidationError("SUPERSEDE must change state")
    elif result is not None and canonical_value(str(result)) != canonical_value(prior):
        raise ValidationError(f"{parsed} cannot change state")
    if scan_prohibited_keys({key: value for key, value in row.items() if key not in {"action", "resulting_value"}}):
        raise ValidationError("source mapping or construction leakage detected")


def validate_annotations(
    items_path: Path,
    annotations_path: Path,
    report_path: Path | None = None,
    minimum_annotators: int = 3,
) -> dict[str, Any]:
    items = {row["blind_id"]: row for row in iter_jsonl(items_path)}
    rows = list(iter_jsonl(annotations_path))
    seen: set[tuple[str, str]] = set()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        blind_id = row.get("blind_id")
        if blind_id not in items:
            raise ValidationError(f"unknown blind_id: {blind_id}")
        validate_annotation_row(row, items[blind_id])
        key = (str(blind_id), str(row["annotator_pseudonym"]))
        if key in seen:
            raise ValidationError(f"duplicate annotator row: {key}")
        seen.add(key)
        grouped[str(blind_id)].append(row)
    under = {blind_id: len(grouped[blind_id]) for blind_id in items if len(grouped[blind_id]) < minimum_annotators}
    if under:
        raise ValidationError(f"too few annotators: {under}")
    report = {
        "items": len(items),
        "annotation_rows": len(rows),
        "minimum_annotators": minimum_annotators,
        "distinct_annotators": len({row["annotator_pseudonym"] for row in rows}),
        "actions": dict(Counter(row["action"] for row in rows if not row.get("exclude"))),
        "exclusions": sum(bool(row.get("exclude")) for row in rows),
        "row_hashes": {row_hash(row): row["blind_id"] for row in rows},
        "status": "VALID",
    }
    if report_path:
        write_json(report_path, report)
    return report

