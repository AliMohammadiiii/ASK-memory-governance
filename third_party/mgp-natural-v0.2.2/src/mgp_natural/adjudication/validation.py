"""Validate adjudications without mutating original annotation rows."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from mgp_natural.annotation.validation import row_hash
from mgp_natural.errors import ValidationError
from mgp_natural.ontology.contract import Action, canonical_value
from mgp_natural.util.io import iter_jsonl, write_json

ADJUDICATION_PROTOCOL_VERSION = "1.0-prospective"
ANNOTATOR_MANUAL_VERSION = "1.0-prospective"


def validate_adjudications(
    items_path: Path,
    annotations_path: Path,
    adjudications_path: Path,
    report_path: Path | None = None,
) -> dict[str, Any]:
    items = {row["blind_id"]: row for row in iter_jsonl(items_path)}
    annotations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in iter_jsonl(annotations_path):
        annotations[row["blind_id"]].append(row)
    adjudications = list(iter_jsonl(adjudications_path))
    seen: set[str] = set()
    for row in adjudications:
        if row.get("protocol_version") != ADJUDICATION_PROTOCOL_VERSION:
            raise ValidationError("adjudication protocol version mismatch")
        if row.get("manual_version") != ANNOTATOR_MANUAL_VERSION:
            raise ValidationError("annotator manual version mismatch")
        blind_id = row.get("blind_id")
        if not isinstance(blind_id, str) or not blind_id:
            raise ValidationError("adjudication requires blind_id")
        if blind_id not in items:
            raise ValidationError("adjudication references unknown item")
        if blind_id in seen:
            raise ValidationError("duplicate adjudication")
        seen.add(blind_id)
        source = annotations.get(blind_id, [])
        if len(source) < 3 or len({r["annotator_pseudonym"] for r in source}) < 3:
            raise ValidationError("adjudication requires three distinct source annotators")
        adjudicator = row.get("adjudicator_pseudonym")
        if not isinstance(adjudicator, str) or not adjudicator.strip():
            raise ValidationError("adjudicator is required")
        if adjudicator in {r["annotator_pseudonym"] for r in source}:
            raise ValidationError("adjudicator must be separate")
        expected_hashes = sorted(row_hash(source_row) for source_row in source)
        if sorted(row.get("source_annotation_hashes", [])) != expected_hashes:
            raise ValidationError("wrong annotation hashes or mutated annotations")
        expected_actions = sorted(str(r.get("action")) for r in source if not r.get("exclude"))
        if sorted(row.get("source_action_multiset", [])) != expected_actions:
            raise ValidationError("wrong source action multiset")
        exclusions = sum(bool(r.get("exclude")) for r in source)
        if row.get("source_exclusion_count") != exclusions:
            raise ValidationError("wrong exclusion count")
        excluded = row.get("final_exclude") is True
        action = row.get("final_action")
        if excluded == (action is not None):
            raise ValidationError("adjudication requires final action xor exclusion")
        if excluded:
            if not str(row.get("final_exclusion_reason") or "").strip():
                raise ValidationError("final exclusion reason required")
            continue
        if not isinstance(action, str):
            raise ValidationError("invalid final action")
        try:
            parsed = Action(action)
        except (TypeError, ValueError) as exc:
            raise ValidationError("invalid final action") from exc
        evidence = row.get("final_evidence_turn_ids")
        turn_ids = {turn["turn_id"] for turn in items[blind_id]["dialogue"]}
        if not isinstance(evidence, list) or not evidence or any(e not in turn_ids for e in evidence):
            raise ValidationError("invalid adjudicated evidence")
        if items[blind_id]["candidate_turn_id"] not in evidence:
            raise ValidationError("candidate evidence is required")
        result = row.get("final_resulting_value")
        prior = items[blind_id]["prior_value"]
        if parsed is Action.SUPERSEDE:
            if not isinstance(result, str) or not result.strip() or canonical_value(result) == canonical_value(prior):
                raise ValidationError("adjudicated SUPERSEDE requires changed state")
        elif result is not None and canonical_value(str(result)) != canonical_value(prior):
            raise ValidationError("KEEP/ABSTAIN must preserve prior")
    missing = set(items) - seen
    if missing:
        raise ValidationError(f"incomplete adjudication coverage: {len(missing)} items")
    report = {"items": len(items), "adjudications": len(adjudications), "status": "VALID"}
    if report_path:
        write_json(report_path, report)
    return report

