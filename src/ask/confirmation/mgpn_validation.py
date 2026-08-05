"""Semantic validation for future MGP-Natural human annotation artifacts."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .blinding import canonical_hash

ACTIONS = frozenset({"KEEP", "SUPERSEDE", "ABSTAIN"})


def _schema_errors(rows: list[dict[str, Any]], schema: dict[str, Any], kind: str) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for index, row in enumerate(rows):
        for error in validator.iter_errors(row):
            path = ".".join(str(part) for part in error.absolute_path) or "$"
            errors.append(f"{kind} row {index} {path}: {error.message}")
    return errors


def validate_annotation_set(
    packet: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
    annotation_schema: dict[str, Any],
    *,
    minimum_annotators: int = 3,
) -> dict[str, Any]:
    """Validate independent annotation coverage and MGP transition semantics."""

    errors = _schema_errors(annotations, annotation_schema, "annotation")
    packet_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(packet):
        blind_id = item.get("blind_id")
        if not isinstance(blind_id, str) or not blind_id:
            errors.append(f"packet row {index} has an empty blind_id")
        elif blind_id in packet_by_id:
            errors.append(f"duplicate packet blind_id: {blind_id}")
        else:
            packet_by_id[blind_id] = item

    seen_pairs: set[tuple[str, str]] = set()
    rows_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(annotations):
        blind_id = str(row.get("blind_id", ""))
        annotator = str(row.get("annotator_pseudonym", ""))
        pair = (blind_id, annotator)
        if pair in seen_pairs:
            errors.append(f"duplicate annotation pair at row {index}: {blind_id}/{annotator}")
        seen_pairs.add(pair)
        if blind_id not in packet_by_id:
            errors.append(f"annotation row {index} references unknown blind_id: {blind_id}")
            continue
        rows_by_id[blind_id].append(row)

        if "exclude_reason" in row:
            continue
        item = packet_by_id[blind_id]
        context_value = item.get("context")
        context = context_value if isinstance(context_value, dict) else {}
        dialogue_value = context.get("dialogue")
        dialogue = dialogue_value if isinstance(dialogue_value, list) else []
        turn_ids = {
            str(turn.get("turn_id"))
            for turn in dialogue
            if isinstance(turn, dict) and turn.get("turn_id") is not None
        }
        candidate_value = item.get("candidate")
        candidate = candidate_value if isinstance(candidate_value, dict) else {}
        candidate_turn_id = str(candidate.get("turn_id", ""))
        evidence = row.get("evidence_turn_ids")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{blind_id}/{annotator}: labeled row requires evidence_turn_ids")
        else:
            evidence_ids = {str(value) for value in evidence}
            unknown = sorted(evidence_ids - turn_ids)
            if unknown:
                errors.append(f"{blind_id}/{annotator}: unknown evidence turns: {unknown}")
            if candidate_turn_id not in evidence_ids:
                errors.append(f"{blind_id}/{annotator}: candidate turn must be evidence")

        predecessor_value = item.get("predecessor")
        predecessor = predecessor_value if isinstance(predecessor_value, dict) else {}
        standing_value = predecessor.get("standing_value")
        resulting_value = row.get("resulting_value")
        action = row.get("action")
        if action in {"KEEP", "ABSTAIN"} and resulting_value != standing_value:
            errors.append(f"{blind_id}/{annotator}: {action} must preserve standing_value")
        if action == "SUPERSEDE" and (
            not isinstance(resulting_value, str)
            or not resulting_value.strip()
            or resulting_value == standing_value
        ):
            errors.append(f"{blind_id}/{annotator}: SUPERSEDE requires a distinct resulting_value")

    for blind_id in packet_by_id:
        rows = rows_by_id.get(blind_id, [])
        annotators = {str(row.get("annotator_pseudonym", "")) for row in rows}
        if len(annotators) < minimum_annotators:
            errors.append(
                f"{blind_id}: requires {minimum_annotators} independent annotators; "
                f"found {len(annotators)}"
            )

    return {
        "status": "VALID" if not errors else "INVALID",
        "packet_item_count": len(packet_by_id),
        "annotation_row_count": len(annotations),
        "minimum_annotators": minimum_annotators,
        "error_count": len(errors),
        "errors": errors,
    }


def validate_adjudication_set(
    annotations: list[dict[str, Any]],
    adjudications: list[dict[str, Any]],
    adjudication_schema: dict[str, Any],
) -> dict[str, Any]:
    """Verify that adjudication is additive and bound to immutable source rows."""

    errors = _schema_errors(adjudications, adjudication_schema, "adjudication")
    annotation_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in annotations:
        annotation_by_id[str(row.get("blind_id", ""))].append(row)
    seen_ids: set[str] = set()
    for index, row in enumerate(adjudications):
        blind_id = str(row.get("blind_id", ""))
        if blind_id in seen_ids:
            errors.append(f"duplicate adjudication blind_id at row {index}: {blind_id}")
        seen_ids.add(blind_id)
        originals = annotation_by_id.get(blind_id, [])
        if len(originals) < 3:
            errors.append(f"{blind_id}: adjudication requires at least three original annotations")
            continue
        original_annotators = {str(item.get("annotator_pseudonym", "")) for item in originals}
        if len(original_annotators) < 3:
            errors.append(f"{blind_id}: adjudication requires three distinct annotators")
        adjudicator = str(row.get("adjudicator_pseudonym", ""))
        if adjudicator in original_annotators:
            errors.append(f"{blind_id}: adjudicator must be separate from original annotators")
        expected_hashes = {canonical_hash(item) for item in originals}
        supplied_hashes = set(map(str, row.get("original_annotation_sha256") or []))
        if supplied_hashes != expected_hashes:
            errors.append(f"{blind_id}: immutable original annotation hashes do not match")
        expected_actions = Counter(
            str(item.get("action")) for item in originals if item.get("action") in ACTIONS
        )
        supplied_actions = Counter(map(str, row.get("original_actions") or []))
        if supplied_actions != expected_actions:
            errors.append(f"{blind_id}: original_actions do not match source annotations")
        expected_exclusions = sum("exclude_reason" in item for item in originals)
        if row.get("original_exclusion_count") != expected_exclusions:
            errors.append(f"{blind_id}: original_exclusion_count does not match source annotations")

    missing_adjudications = sorted(set(annotation_by_id) - seen_ids)
    if missing_adjudications:
        errors.append(
            f"adjudication coverage is incomplete; missing blind IDs: {missing_adjudications[:5]}"
        )

    return {
        "status": "VALID" if not errors else "INVALID",
        "adjudication_row_count": len(adjudications),
        "complete_coverage": not missing_adjudications,
        "error_count": len(errors),
        "errors": errors,
    }
