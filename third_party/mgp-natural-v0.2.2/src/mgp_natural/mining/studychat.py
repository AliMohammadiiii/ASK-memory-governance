"""Two-stage deterministic StudyChat candidate construction.

The constructor is deliberately conservative. Its outputs are provisional
construction judgments and are never publication-eligible gold.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from re import Pattern
from typing import Any

from mgp_natural.errors import ValidationError
from mgp_natural.ontology.contract import validate_construction_item
from mgp_natural.reconstruction.studychat import reconstruct_candidate_context
from mgp_natural.util.io import iter_jsonl, write_json, write_jsonl
from mgp_natural.util.text import canonicalize_text


@dataclass(frozen=True)
class SlotRule:
    slot: str
    scope: str
    pattern_values: tuple[tuple[Pattern[str], str], ...]


SLOT_RULES: tuple[SlotRule, ...] = (
    SlotRule(
        "response_length",
        "SESSION_INTERACTION_PREFERENCE",
        (
            (
                re.compile(
                    r"(?i)\b(?:please\s+)?(?:be|keep(?:ing)?\s+(?:it|(?:the\s+)?answers?)|"
                    r"make\s+(?:it|answers?)|continue(?:\s+keeping)?\s+(?:the\s+)?answers?)"
                    r"\s+(?:very\s+)?(?:brief|concise|short)\b"
                ),
                "concise",
            ),
            (
                re.compile(
                    r"(?i)\b(?:please\s+)?(?:be|make\s+(?:it|answers?))\s+"
                    r"(?:more\s+)?(?:detailed|thorough|long)\b"
                ),
                "detailed",
            ),
            (
                re.compile(
                    r"(?i)\b(?:give|provide|write|keep)\b.{0,24}\b"
                    r"(?:brief|concise)\s+(?:answer|response|explanation)s?\b"
                ),
                "concise",
            ),
        ),
    ),
    SlotRule(
        "code_assistance_policy",
        "SESSION_INTERACTION_PREFERENCE",
        (
            (
                re.compile(
                    r"(?i)\b(?:do\s+not|don't|dont|without)\s+"
                    r"(?:give|provide|write|show)(?:\s+me)?\s+(?:the\s+)?"
                    r"(?:full\s+|complete\s+)?code\b"
                ),
                "no_complete_code",
            ),
            (
                re.compile(r"(?i)\b(?:hints?|guidance)\s+(?:only|instead\s+of\s+code)\b"),
                "hints_only",
            ),
            (
                re.compile(
                    r"(?i)\b(?:give|provide|write|show)(?:\s+me)?\s+(?:the\s+)?"
                    r"(?:full|complete)\s+code\b"
                ),
                "complete_code_allowed",
            ),
            (re.compile(r"(?i)\bcode\s+only\b"), "code_only"),
        ),
    ),
    SlotRule(
        "explanation_style",
        "SESSION_INTERACTION_PREFERENCE",
        (
            (
                re.compile(
                    r"(?i)\b(?:explain|show|walk|guide|teach|break)\b.{0,40}"
                    r"\bstep[- ]by[- ]step\b|\bstep[- ]by[- ]step\s+guidance\b"
                ),
                "step_by_step",
            ),
            (
                re.compile(
                    r"(?i)\b(?:explain|describe|write|answer)\b.{0,30}"
                    r"\b(?:easy|simple|plain)\s+(?:terms|language)\b"
                ),
                "plain_language",
            ),
            (
                re.compile(r"(?i)\b(?:explain|explanation)\s+(?:first|before\s+(?:the\s+)?code)\b"),
                "explanation_first",
            ),
        ),
    ),
    SlotRule(
        "output_format",
        "SESSION_INTERACTION_PREFERENCE",
        (
            (
                re.compile(
                    r"(?i)\b(?:show|give|provide|return|respond|answer|format)\b.{0,40}"
                    r"\bnot\s+(?:in|as)\s+(?:valid\s+)?json\b|"
                    r"\b(?:not\s+(?:in|as)|without)\s+(?:valid\s+)?json\b"
                ),
                "plain_text",
            ),
            (
                re.compile(
                    r"(?i)\b(?:convert|format|present|show|give|put|return|respond|answer)\b"
                    r".{0,40}\b(?:as|in|into)?\s*(?:a\s+)?markdown\s+table\b|"
                    r"\b(?:as|in)\s+(?:a\s+)?markdown\s+table\b"
                ),
                "markdown_table",
            ),
            (
                re.compile(
                    r"(?i)\b(?:use|write|format|present|show|give|return|respond|answer)\b"
                    r".{0,40}\b(?:as|in)?\s*(?:a\s+)?bullet(?:ed)?\s+(?:points|list)\b|"
                    r"\b(?:as|in)\s+(?:a\s+)?bullet(?:ed)?\s+(?:points|list)\b"
                ),
                "bullet_list",
            ),
            (
                re.compile(
                    r"(?i)\b(?:write|format|present|show|give|return|respond|answer)\b"
                    r".{0,40}\b(?:as|in)?\s*(?:a\s+)?(?:single|one)\s+paragraph\b|"
                    r"\b(?:as|in)\s+(?:a\s+)?(?:single|one)\s+paragraph\b"
                ),
                "single_paragraph",
            ),
            (
                re.compile(
                    r"(?i)\b(?:return|respond|answer|show|give|provide|output|format)\b"
                    r".{0,40}\b(?:as|in)?\s*(?:valid\s+)?json(?:\s+only)?\b|"
                    r"\b(?:as|in)\s+(?:valid\s+)?json(?:\s+only)?\b"
                ),
                "json",
            ),
        ),
    ),
)
FILE_RE = re.compile(r"(?i)(?<![\w.-])([A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:csv|jsonl?|parquet|txt|py|ipynb|tsv|xlsx?))(?=$|[\s,;:!?()\[\]{}\"'']|\.(?=\s|$))")
EXPLICIT_UPDATE = re.compile(
    r"(?i)\b(?:actually|instead|rather\s+than|from\s+now\s+on|no\s+longer|i\s+meant|"
    r"switch(?:ing)?\s+to|use\s+.{0,80}\s+instead|not\s+(?:in|as)\s+json)\b"
)
UNCERTAINTY = re.compile(
    r"(?i)\b(?:maybe|perhaps|(?:i(?:'m|\s+am)?\s+)?not\s+sure|uncertain|"
    r"might\s+(?:use|switch)|could\s+(?:use|switch)|"
    r"consider(?:ing)?\s+(?:using|switching))\b"
)
CONDITIONAL_STATE = re.compile(
    r"(?i)\bif\s+(?:this|that|it)\s+is\s+(?:my|the|our)?\s*"
    r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:csv|jsonl?|parquet|txt|py|ipynb|tsv|xlsx?)\b|"
    r"\bif\s+(?:we|i)\s+(?:use|switch|choose)\b"
)
REAFFIRM = re.compile(r"(?i)\b(?:continue|keep|still|as before|same|exactly|yes)\b")
PURE_ACK = re.compile(r"(?i)^\s*(?:ok(?:ay)?|thanks?|thank you|got it|yes|no|cool|great)[.!\s]*$")
ASSIGNMENT_ONLY = re.compile(r"(?i)\b(?:assignment|rubric|instructions?|points|submission|due date)\b")
STATE_SIGNAL = re.compile(
    r"(?i)\b(?:actually|instead|i meant|rather than|no longer|do not|don't|dont|keep|continue|"
    r"maybe|perhaps|not sure|use|switch|format|brief|concise|step[- ]by[- ]step|rollback|revert)\b"
)


def stage1_signals(text: str) -> list[str]:
    signals = []
    checks = {
        "EXPLICIT_UPDATE": EXPLICIT_UPDATE,
        "UNCERTAINTY": UNCERTAINTY,
        "REAFFIRMATION": REAFFIRM,
        "PREFERENCE_OR_STATE": STATE_SIGNAL,
        "FILE_REFERENCE": FILE_RE,
    }
    for name, pattern in checks.items():
        if pattern.search(text):
            signals.append(name)
    return signals


def _extract_slot_values(text: str) -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    for rule in SLOT_RULES:
        for pattern, value in rule.pattern_values:
            if pattern.search(text):
                found.append((rule.slot, rule.scope, value))
                break
    files = FILE_RE.findall(text)
    if files:
        latest = files[-1]
        slot = "active_dataset_file" if latest.lower().endswith((".csv", ".tsv", ".parquet", ".xlsx", ".xls")) else "active_artifact_file"
        found.append((slot, "ARTIFACT_STATE", latest))
    return found


def _turn_hash(row: dict[str, Any]) -> str:
    basis = f"{row['chat_id_hash']}:{row['row_index']}:{row['interaction_count']}"
    return hashlib.sha256(basis.encode()).hexdigest()[:24]


def _build_rejection(row: dict[str, Any], reason: str, signals: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "item_id": f"SC-{_turn_hash(row)}",
        "source_track": "STUDYCHAT",
        "construction_status": "REJECTED",
        "rejection_reason": reason,
        "stage1_signals": signals,
        "source_locator_private": {
            "row_index": row["row_index"],
            "user_id_hash": row["user_id_hash"],
            "chat_id_hash": row["chat_id_hash"],
        },
    }


def construct_candidate(row: dict[str, Any]) -> dict[str, Any]:
    prompt = row["prompt"]
    signals = stage1_signals(prompt)
    if PURE_ACK.fullmatch(prompt):
        return _build_rejection(row, "PURE_ACKNOWLEDGMENT", signals)
    if not signals:
        if ASSIGNMENT_ONLY.search(prompt):
            return _build_rejection(row, "ASSIGNMENT_INSTRUCTION_ONLY", signals)
        return _build_rejection(row, "NO_STATEFUL_CONTENT", signals)
    turns = reconstruct_candidate_context(row)
    candidate_id = turns[-1]["turn_id"]
    candidate_values = _extract_slot_values(prompt)
    if not candidate_values:
        if ASSIGNMENT_ONLY.search(prompt):
            return _build_rejection(row, "ASSIGNMENT_INSTRUCTION_ONLY", signals)
        return _build_rejection(row, "NON_ATOMIC_CANDIDATE", signals)
    # Exactly one slot is required. Multiple mentions of the same slot collapse to the last value.
    by_slot: dict[str, tuple[str, str]] = {}
    for slot, scope, value in candidate_values:
        by_slot[slot] = (scope, value)
    if len(by_slot) != 1:
        return _build_rejection(row, "NON_ATOMIC_CANDIDATE", signals)
    slot, (scope, candidate_value) = next(iter(by_slot.items()))
    prior_evidence: tuple[str, str] | None = None
    for turn in reversed(turns[:-1]):
        if turn["role"] != "user":
            continue
        for prior_slot, _, prior_value in _extract_slot_values(turn["text"]):
            if prior_slot == slot:
                prior_evidence = (turn["turn_id"], prior_value)
                break
        if prior_evidence:
            break
    if prior_evidence is None:
        return _build_rejection(row, "NO_PRIOR_STATE", signals)
    prior_turn_id, prior_value = prior_evidence
    prior_canonical = canonicalize_text(prior_value)
    candidate_canonical = canonicalize_text(candidate_value)
    if UNCERTAINTY.search(prompt):
        action = "ABSTAIN"
        resulting = prior_value
        relation = "WITHHOLDS_COMMITMENT"
        effective_scope = "UNCERTAINTY_STATE"
    elif candidate_canonical == prior_canonical:
        action = "KEEP"
        resulting = prior_value
        relation = "REAFFIRMS"
        effective_scope = scope
    elif EXPLICIT_UPDATE.search(prompt):
        action = "SUPERSEDE"
        resulting = candidate_value
        relation = "SUPERSEDES"
        effective_scope = "CORRECTION_STATE" if "EXPLICIT_UPDATE" in signals else scope
    else:
        return _build_rejection(row, "RESULTING_VALUE_UNRESOLVED", signals)
    first_context_index = max(0, len(turns) - 7)
    context = turns[first_context_index:]
    context_ids = [turn["turn_id"] for turn in context]
    if prior_turn_id not in context_ids:
        prior_turn = next(turn for turn in turns if turn["turn_id"] == prior_turn_id)
        context = [prior_turn, *context]
        context_ids = [turn["turn_id"] for turn in context]
    item = {
        "schema_version": "1.0",
        "item_id": f"SC-{_turn_hash(row)}",
        "blind_id": None,
        "source_track": "STUDYCHAT",
        "scope": effective_scope,
        "principal_type": "PSEUDONYMOUS_USER",
        "memory_slot": slot,
        "prior_value": prior_value,
        "candidate_value": candidate_value,
        "dialogue": context,
        "prior_evidence_turn_ids": [prior_turn_id],
        "candidate_turn_id": candidate_id,
        "context_turn_ids": context_ids,
        "constructor_provisional_action": action,
        "constructor_provisional_resulting_value": resulting,
        "constructor_rationale": (
            f"Deterministic provisional construction: {relation} for slot {slot}; "
            "requires independent semantic and privacy review."
        ),
        "lineage_relation_private": relation,
        "stage1_signals": signals,
        "source_locator_private": {
            "row_index": row["row_index"],
            "interaction_count": row["interaction_count"],
            "user_id_hash": row["user_id_hash"],
            "chat_id_hash": row["chat_id_hash"],
        },
        "continuity_keys_private": [
            f"user:{row['user_id_hash']}",
            f"chat:{row['chat_id_hash']}",
        ],
        "privacy_status": "PENDING_HUMAN_REVIEW",
        "construction_status": "CANDIDATE",
        "rejection_reason": None,
    }
    validate_construction_item(item)
    return item


def mine_file(input_path: Path, candidates_path: Path, rejections_path: Path, report_path: Path) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    seen_candidate_keys: set[tuple[str, str, str]] = set()
    for row in iter_jsonl(input_path):
        try:
            item = construct_candidate(row)
        except (KeyError, TypeError, ValidationError):
            prompt = row.get("prompt") if isinstance(row, dict) else ""
            signals = stage1_signals(prompt) if isinstance(prompt, str) else []
            item = _build_rejection(row, "SOURCE_INCOMPLETE", signals)
        if item["construction_status"] == "REJECTED":
            rejections.append(item)
            continue
        key = (
            item["source_locator_private"]["chat_id_hash"],
            item["candidate_turn_id"],
            item["memory_slot"],
        )
        if key in seen_candidate_keys:
            rejections.append(_build_rejection(row, "DUPLICATE", item["stage1_signals"]))
            continue
        seen_candidate_keys.add(key)
        candidates.append(item)
    write_jsonl(candidates_path, candidates, mode=0o600)
    write_jsonl(rejections_path, rejections, mode=0o600)
    report = {
        "schema_version": "1.0",
        "input_rows": len(candidates) + len(rejections),
        "candidates": len(candidates),
        "rejected": len(rejections),
        "scope_counts": dict(Counter(item["scope"] for item in candidates)),
        "action_counts_provisional_only": dict(
            Counter(item["constructor_provisional_action"] for item in candidates)
        ),
        "rejection_reasons": dict(Counter(item["rejection_reason"] for item in rejections)),
        "publication_eligible": False,
        "review_status": "INDEPENDENT_CONSTRUCTION_AND_PRIVACY_REVIEW_REQUIRED",
    }
    write_json(report_path, report)
    return report


@dataclass(frozen=True)
class StateMention:
    slot: str
    scope: str
    value: str
    extractor: str


_FILE_TOKEN = r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:csv|jsonl?|parquet|txt|py|ipynb|tsv|xlsx?)"
_FILE_UPDATE_PATTERNS: tuple[tuple[str, Pattern[str]], ...] = (
    (
        "USE_NEW_INSTEAD_OF_OLD",
        re.compile(rf"(?i)\buse\s+(?P<new>{_FILE_TOKEN})\s+(?:instead\s+of|rather\s+than)\s+(?P<old>{_FILE_TOKEN})\b"),
    ),
    (
        "INSTEAD_OF_OLD_USE_NEW",
        re.compile(rf"(?i)\binstead\s+of\s+(?P<old>{_FILE_TOKEN})[,;:]?\s+(?:please\s+)?use\s+(?P<new>{_FILE_TOKEN})\b"),
    ),
    (
        "SWITCH_FROM_TO",
        re.compile(rf"(?i)\bswitch(?:ing)?\s+from\s+(?P<old>{_FILE_TOKEN})\s+to\s+(?P<new>{_FILE_TOKEN})\b"),
    ),
    (
        "SWITCH_TO",
        re.compile(rf"(?i)\bswitch(?:ing)?\s+to\s+(?P<new>{_FILE_TOKEN})\b"),
    ),
    (
        "ACTUALLY_USE",
        re.compile(rf"(?i)\bactually[, ]+(?:please\s+)?use\s+(?P<new>{_FILE_TOKEN})\b"),
    ),
    (
        "I_MEANT_FILE",
        re.compile(rf"(?i)\bi\s+meant(?:\s+to\s+use)?\s+(?P<new>{_FILE_TOKEN})\b"),
    ),
    (
        "USE_FILE_INSTEAD",
        re.compile(rf"(?i)\buse\s+(?P<new>{_FILE_TOKEN})\s+instead\b"),
    ),
)
_FILE_STATE_PATTERNS: tuple[tuple[str, str, Pattern[str]], ...] = (
    (
        "editable_artifact_file",
        "ARTIFACT_STATE",
        re.compile(
            rf"(?i)\b(?:do\s+not|don't|dont)\s+(?:make|apply)\s+(?:any\s+)?changes?\s+to\s+(?:any\s+)?files?\s+other\s+than\s+(?P<file>{_FILE_TOKEN})\b"
        ),
    ),
    (
        "protected_artifact_file",
        "ARTIFACT_STATE",
        re.compile(
            rf"(?i)\bwithout\s+(?:making|applying)\s+(?:any\s+)?changes?\s+to\s+(?P<file>{_FILE_TOKEN})\b"
        ),
    ),
    (
        "active_artifact_file",
        "ARTIFACT_STATE",
        re.compile(
            rf"(?i)\bstart\s+from\s+(?:the\s+)?(?:original|current|latest|revised)?\s*(?:code\s+)?(?:i\s+provided\s+)?(?:for|in)\s+(?P<file>{_FILE_TOKEN})\b"
        ),
    ),
    (
        "active_artifact_file",
        "ARTIFACT_STATE",
        re.compile(
            rf"(?i)\b(?:here(?:'s|\s+is)|this\s+is)\s+(?:my|the|our|an|updated|revised|current|new|original)?\s*(?P<file>{_FILE_TOKEN})\b"
        ),
    ),
    (
        "active_file",
        "ARTIFACT_STATE",
        re.compile(
            rf"(?i)\b(?:please\s+)?(?:use|continue\s+using|keep\s+using|work\s+(?:on|with)|focus\s+on|load|open)\s+(?:the\s+)?(?P<file>{_FILE_TOKEN})\b"
        ),
    ),
)
_DIRECT_USER_OVERRIDE = re.compile(
    r"(?i)\b(?:please|i\s+(?:want|need|prefer|meant)|actually|instead|from\s+now\s+on|do\s+not|don't|dont|keep|continue|switch)\b"
)
_ASSIGNMENT_QUOTATION = re.compile(
    r"(?im)\b(?:the\s+)?(?:assignment|rubric|instructions?)\s+"
    r"(?:says?|requires?|asks?)\b|"
    r"\bmy\s+(?:professor|instructor)\s+(?:asked|asks|wants|required)\b|"
    r"\b(?:your\s+task|todo|report\s+section|project\s+prompt)\b|"
    r"(?:^|\n)\s*(?:#{1,6}\s*)?part\s+\d+(?:\.\d+)?\b|"
    r"(?:^|\n)\s*(?:readme\.md:\s*)?(?:#{1,6}\s*)?assignment\b|"
    r"\b(?:paste|copy)\b.{0,100}\b(?:cell|submission|assignment)\b"
)


def _slot_for_file(filename: str, fallback: str = "active_file") -> tuple[str, str]:
    lower = filename.casefold()
    if lower.endswith((".csv", ".tsv", ".parquet", ".xlsx", ".xls")):
        return "active_dataset_file", "ARTIFACT_STATE"
    if fallback == "active_file":
        return "active_artifact_file", "ARTIFACT_STATE"
    return fallback, "ARTIFACT_STATE"


def extract_explicit_states(text: str) -> list[StateMention]:
    """Extract only explicit state-bearing statements, not bare file references."""

    mentions: list[StateMention] = []
    for rule in SLOT_RULES:
        for pattern, value in rule.pattern_values:
            if pattern.search(text):
                mentions.append(StateMention(rule.slot, rule.scope, value, "PREFERENCE_RULE"))
                break

    for name, pattern in _FILE_UPDATE_PATTERNS:
        match = pattern.search(text)
        if match:
            filename = match.group("new")
            slot, scope = _slot_for_file(filename)
            mentions.append(StateMention(slot, scope, filename, name))
            return mentions

    for requested_slot, scope, pattern in _FILE_STATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        filename = match.group("file")
        slot = requested_slot
        if requested_slot == "active_file":
            slot, scope = _slot_for_file(filename)
        mentions.append(StateMention(slot, scope, filename, pattern.pattern[:48]))
    # Stable de-duplication. Multiple values for one slot remain visible and fail atomicity later.
    seen: set[tuple[str, str, str]] = set()
    result = []
    for mention in mentions:
        key = (mention.slot, mention.scope, canonicalize_text(mention.value))
        if key not in seen:
            seen.add(key)
            result.append(mention)
    return result


def _canonical_turn_id(interaction_count: int, role: str) -> str:
    offset = 1 if role == "user" else 2
    return f"T{2 * interaction_count + offset:05d}"


def _rejection_from_chat(
    chat: dict[str, Any],
    interaction: dict[str, Any],
    reason: str,
    signals: list[str],
) -> dict[str, Any]:
    basis = (
        f"{chat['source_chat_private']}:{interaction['interaction_count']}:"
        f"{','.join(str(value) for value in interaction.get('row_indices_private', []))}"
    )
    item_id = "SC-" + hashlib.sha256(basis.encode()).hexdigest()[:24]
    return {
        "schema_version": "1.0",
        "item_id": item_id,
        "source_track": "STUDYCHAT",
        "construction_status": "REJECTED",
        "rejection_reason": reason,
        "stage1_signals": signals,
        "source_locator_private": {
            "interaction_count": interaction["interaction_count"],
            "row_indices": interaction.get("row_indices_private", []),
            "user_id_hash": chat["source_user_private"],
            "chat_id_hash": chat["source_chat_private"],
        },
    }


def _candidate_item_from_chat(
    chat: dict[str, Any],
    interaction: dict[str, Any],
    prior: dict[str, Any],
    mention: StateMention,
    action: str,
    relation: str,
    signals: list[str],
) -> dict[str, Any]:
    count = interaction["interaction_count"]
    prior_count = prior["interaction_count"]
    basis = (
        f"{chat['source_chat_private']}:{count}:"
        f"{','.join(str(value) for value in interaction.get('row_indices_private', []))}:"
        f"{mention.slot}"
    )
    item_id = "SC-" + hashlib.sha256(basis.encode()).hexdigest()[:24]
    interactions = chat["interactions"]
    by_count = {entry["interaction_count"]: entry for entry in interactions}
    local_counts = [value for value in range(max(0, count - 3), count) if value in by_count]
    if prior_count not in local_counts:
        local_counts.insert(0, prior_count)
    dialogue: list[dict[str, str]] = []
    for value in local_counts:
        entry = by_count[value]
        dialogue.append(
            {
                "turn_id": _canonical_turn_id(value, "user"),
                "role": "user",
                "text": entry["prompt"],
            }
        )
        dialogue.append(
            {
                "turn_id": _canonical_turn_id(value, "assistant"),
                "role": "assistant",
                "text": entry["response"],
            }
        )
    candidate_turn_id = _canonical_turn_id(count, "user")
    dialogue.append({"turn_id": candidate_turn_id, "role": "user", "text": interaction["prompt"]})
    prior_turn_id = _canonical_turn_id(prior_count, "user")
    prior_value = prior["value"]
    resulting = mention.value if action == "SUPERSEDE" else prior_value
    scope = mention.scope
    if action == "SUPERSEDE":
        scope = "CORRECTION_STATE"
    elif action == "ABSTAIN":
        scope = "UNCERTAINTY_STATE"
    item = {
        "schema_version": "1.0",
        "item_id": item_id,
        "blind_id": None,
        "source_track": "STUDYCHAT",
        "scope": scope,
        "principal_type": "PSEUDONYMOUS_USER",
        "memory_slot": mention.slot,
        "prior_value": prior_value,
        "candidate_value": mention.value,
        "dialogue": dialogue,
        "prior_evidence_turn_ids": [prior_turn_id],
        "candidate_turn_id": candidate_turn_id,
        "context_turn_ids": [turn["turn_id"] for turn in dialogue],
        "constructor_provisional_action": action,
        "constructor_provisional_resulting_value": resulting,
        "constructor_rationale": (
            f"Conservative deterministic construction: {relation} for atomic slot "
            f"{mention.slot}; independent semantic and privacy review remains required."
        ),
        "lineage_relation_private": relation,
        "stage1_signals": signals,
        "source_locator_private": {
            "interaction_count": count,
            "row_indices": interaction.get("row_indices_private", []),
            "user_id_hash": chat["source_user_private"],
            "chat_id_hash": chat["source_chat_private"],
            "source_completeness": chat["source_completeness"],
        },
        "continuity_keys_private": [
            f"user:{chat['source_user_private']}",
            f"chat:{chat['source_chat_private']}",
        ],
        "privacy_status": "PENDING_HUMAN_REVIEW",
        "construction_status": "CANDIDATE",
        "rejection_reason": None,
    }
    validate_construction_item(item)
    return item


def mine_reconstructed_chats(
    input_path: Path,
    candidates_path: Path,
    rejections_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    seen_candidate_keys: set[tuple[str, int, str]] = set()
    chats = list(iter_jsonl(input_path))
    for chat in chats:
        required = {
            "source_user_private",
            "source_chat_private",
            "topic_private",
            "interactions",
            "source_completeness",
            "reconstruction_status",
        }
        missing = required - set(chat)
        if missing:
            raise ValueError(f"reconstructed StudyChat row missing fields: {sorted(missing)}")
        interactions = sorted(chat["interactions"], key=lambda entry: entry["interaction_count"])
        standing: dict[str, dict[str, Any]] = {}
        observed_counts: set[int] = set()
        for interaction in interactions:
            count = interaction["interaction_count"]
            prompt = interaction["prompt"]
            signals = stage1_signals(prompt)
            mentions = extract_explicit_states(prompt)
            if not signals and not mentions:
                rejection = _rejection_from_chat(chat, interaction, "NO_STATEFUL_CONTENT", signals)
                rejections.append(rejection)
                observed_counts.add(count)
                continue
            if PURE_ACK.fullmatch(prompt):
                rejections.append(_rejection_from_chat(chat, interaction, "PURE_ACKNOWLEDGMENT", signals))
                observed_counts.add(count)
                continue
            if _ASSIGNMENT_QUOTATION.search(prompt):
                rejections.append(
                    _rejection_from_chat(chat, interaction, "ASSIGNMENT_INSTRUCTION_ONLY", signals)
                )
                observed_counts.add(count)
                continue
            if not mentions:
                reason = "ASSIGNMENT_INSTRUCTION_ONLY" if ASSIGNMENT_ONLY.search(prompt) else "NON_ATOMIC_CANDIDATE"
                rejections.append(_rejection_from_chat(chat, interaction, reason, signals))
                observed_counts.add(count)
                continue
            by_slot: dict[str, list[StateMention]] = {}
            for mention in mentions:
                by_slot.setdefault(mention.slot, []).append(mention)
            if len(by_slot) != 1 or any(len(values) != 1 for values in by_slot.values()):
                rejections.append(_rejection_from_chat(chat, interaction, "NON_ATOMIC_CANDIDATE", signals))
                # Uncertain or multi-slot statements do not update standing.
                observed_counts.add(count)
                continue
            mention = next(iter(by_slot.values()))[0]
            prior = standing.get(mention.slot)
            uncertain = bool(UNCERTAINTY.search(prompt) or CONDITIONAL_STATE.search(prompt))
            if prior is None:
                rejections.append(_rejection_from_chat(chat, interaction, "NO_PRIOR_STATE", signals))
                if not uncertain:
                    standing[mention.slot] = {
                        "value": mention.value,
                        "interaction_count": count,
                    }
                observed_counts.add(count)
                continue
            prior_count = prior["interaction_count"]
            if chat["reconstruction_status"] == "CONFLICTED" or any(
                missing_count not in observed_counts for missing_count in range(prior_count + 1, count)
            ):
                rejections.append(_rejection_from_chat(chat, interaction, "SOURCE_INCOMPLETE", signals))
                if not uncertain:
                    standing[mention.slot] = {
                        "value": mention.value,
                        "interaction_count": count,
                    }
                observed_counts.add(count)
                continue
            prior_value = canonicalize_text(prior["value"])
            candidate_value = canonicalize_text(mention.value)
            if uncertain:
                action = "ABSTAIN"
                relation = "WITHHOLDS_COMMITMENT"
            elif candidate_value == prior_value:
                action = "KEEP"
                relation = "REAFFIRMS"
            elif EXPLICIT_UPDATE.search(prompt) or mention.extractor in {
                "USE_NEW_INSTEAD_OF_OLD",
                "INSTEAD_OF_OLD_USE_NEW",
                "SWITCH_FROM_TO",
                "SWITCH_TO",
                "ACTUALLY_USE",
                "I_MEANT_FILE",
                "USE_FILE_INSTEAD",
            }:
                action = "SUPERSEDE"
                relation = "SUPERSEDES"
            else:
                rejections.append(
                    _rejection_from_chat(chat, interaction, "RESULTING_VALUE_UNRESOLVED", signals)
                )
                standing[mention.slot] = {"value": mention.value, "interaction_count": count}
                observed_counts.add(count)
                continue
            item = _candidate_item_from_chat(
                chat, interaction, prior, mention, action, relation, signals
            )
            key = (chat["source_chat_private"], count, mention.slot)
            if key in seen_candidate_keys:
                rejections.append(_rejection_from_chat(chat, interaction, "DUPLICATE", signals))
            else:
                seen_candidate_keys.add(key)
                candidates.append(item)
            if action != "ABSTAIN":
                standing[mention.slot] = {"value": mention.value, "interaction_count": count}
            observed_counts.add(count)

    write_jsonl(candidates_path, candidates, mode=0o600)
    write_jsonl(rejections_path, rejections, mode=0o600)
    report = {
        "schema_version": "1.0",
        "input_chats": len(chats),
        "input_interactions": len(candidates) + len(rejections),
        "candidates": len(candidates),
        "rejected": len(rejections),
        "scope_counts": dict(Counter(item["scope"] for item in candidates)),
        "action_counts_provisional_only": dict(
            Counter(item["constructor_provisional_action"] for item in candidates)
        ),
        "rejection_reasons": dict(Counter(item["rejection_reason"] for item in rejections)),
        "publication_eligible": False,
        "review_status": "INDEPENDENT_CONSTRUCTION_AND_PRIVACY_REVIEW_REQUIRED",
        "messages_used_for_mining": False,
    }
    write_json(report_path, report)
    return report

