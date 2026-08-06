"""Shared task ontology and fail-closed item semantics."""
from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from mgp_natural.errors import ValidationError
from mgp_natural.util.text import canonicalize_text


class Action(StrEnum):
    KEEP = "KEEP"
    SUPERSEDE = "SUPERSEDE"
    ABSTAIN = "ABSTAIN"


class SourceTrack(StrEnum):
    STUDYCHAT = "STUDYCHAT"
    WIKICONV = "WIKICONV"


class ConstructionStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    REJECTED = "REJECTED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class LineageRelation(StrEnum):
    REAFFIRMS = "REAFFIRMS"
    SUPERSEDES = "SUPERSEDES"
    WITHHOLDS_COMMITMENT = "WITHHOLDS_COMMITMENT"
    RESTORES = "RESTORES"
    DELETES = "DELETES"
    RESOLVES = "RESOLVES"
    REOPENS = "REOPENS"
    CONTRADICTS_WITHOUT_RESOLUTION = "CONTRADICTS_WITHOUT_RESOLUTION"


ALLOWED_SCOPES = {
    "SESSION_TASK_STATE",
    "CROSS_SESSION_TASK_STATE",
    "SESSION_INTERACTION_PREFERENCE",
    "CROSS_SESSION_USER_PREFERENCE",
    "ARTIFACT_STATE",
    "CORRECTION_STATE",
    "UNCERTAINTY_STATE",
    "EDITORIAL_DECISION",
    "CONTENT_INCLUSION",
    "CONTENT_REMOVAL",
    "WORDING_STATE",
    "SOURCE_STATUS",
    "CONSENSUS_STATE",
    "DISPUTE_STATE",
    "REVISION_STATE",
    "DELETION_RESTORATION",
    "EDITORIAL_UNCERTAINTY",
}

REJECTION_CODES = {
    "NO_PRIOR_STATE",
    "NO_STATEFUL_CONTENT",
    "SLOT_MISMATCH",
    "PRINCIPAL_MISMATCH",
    "NON_ATOMIC_PRIOR",
    "NON_ATOMIC_CANDIDATE",
    "INSUFFICIENT_CONTEXT",
    "RESULTING_VALUE_UNRESOLVED",
    "PURE_ACKNOWLEDGMENT",
    "ASSIGNMENT_INSTRUCTION_ONLY",
    "DUPLICATE",
    "PRIVACY_UNSAFE",
    "SOURCE_INCOMPLETE",
    "OTHER_DOCUMENTED",
}


def canonical_value(value: str) -> str:
    return canonicalize_text(value)


_NON_ATOMIC_VALUE = re.compile(r"(?i)(?:\?|\b(?:either|or)\b|\b(?:and/or)\b)")


def _validate_atomic_value(value: str, field: str) -> None:
    if _NON_ATOMIC_VALUE.search(value):
        raise ValidationError(f"{field} must be atomic and affirmative")


def _require_nonempty(item: dict[str, Any], key: str) -> None:
    if not isinstance(item.get(key), str) or not item[key].strip():
        raise ValidationError(f"{key} must be a nonempty string")


def validate_construction_item(item: dict[str, Any]) -> None:
    """Validate one private construction item beyond JSON Schema constraints."""
    for key in (
        "schema_version",
        "item_id",
        "source_track",
        "scope",
        "principal_type",
        "memory_slot",
        "prior_value",
        "candidate_turn_id",
        "privacy_status",
        "construction_status",
    ):
        _require_nonempty(item, key)
    try:
        SourceTrack(item["source_track"])
    except ValueError as exc:
        raise ValidationError("invalid source_track") from exc
    if item["scope"] not in ALLOWED_SCOPES:
        raise ValidationError("invalid scope")
    _validate_atomic_value(item["prior_value"], "prior_value")
    candidate_value = item.get("candidate_value")
    if isinstance(candidate_value, str):
        _validate_atomic_value(candidate_value, "candidate_value")
    dialogue = item.get("dialogue")
    if not isinstance(dialogue, list) or not dialogue:
        raise ValidationError("dialogue must be a nonempty list")
    ids = []
    for turn in dialogue:
        if not isinstance(turn, dict):
            raise ValidationError("dialogue turn must be an object")
        for key in ("turn_id", "role", "text"):
            _require_nonempty(turn, key)
        ids.append(turn["turn_id"])
    if len(ids) != len(set(ids)):
        raise ValidationError("turn IDs must be unique")
    if item["candidate_turn_id"] not in ids:
        raise ValidationError("candidate turn must exist")
    prior_ids = item.get("prior_evidence_turn_ids")
    if not isinstance(prior_ids, list) or not prior_ids:
        raise ValidationError("prior evidence is required")
    if any(turn_id not in ids for turn_id in prior_ids):
        raise ValidationError("unknown prior evidence turn")
    candidate_index = ids.index(item["candidate_turn_id"])
    if any(ids.index(turn_id) >= candidate_index for turn_id in prior_ids):
        raise ValidationError("prior evidence must precede candidate")
    status = item["construction_status"]
    action = item.get("constructor_provisional_action")
    result = item.get("constructor_provisional_resulting_value")
    rejection = item.get("rejection_reason")
    if status == ConstructionStatus.REJECTED:
        if rejection not in REJECTION_CODES:
            raise ValidationError("rejected item requires a valid rejection code")
        return
    if rejection is not None:
        raise ValidationError("non-rejected item cannot have rejection_reason")
    if not isinstance(action, str):
        raise ValidationError("candidate item requires a provisional action")
    try:
        parsed = Action(action)
    except (ValueError, TypeError) as exc:
        raise ValidationError("candidate item requires a provisional action") from exc
    prior = canonical_value(item["prior_value"])
    if parsed is Action.SUPERSEDE:
        if not isinstance(result, str) or not result.strip():
            raise ValidationError("SUPERSEDE requires resulting value")
        if canonical_value(result) == prior:
            raise ValidationError("SUPERSEDE resulting value must change")
    elif not isinstance(result, str) or canonical_value(result) != prior:
        raise ValidationError(f"{parsed} must preserve prior state")

