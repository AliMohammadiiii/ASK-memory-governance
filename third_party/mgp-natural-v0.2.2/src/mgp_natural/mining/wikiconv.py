"""Conservative WikiConv editorial candidate construction."""
from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

from mgp_natural.util.io import iter_jsonl, write_json, write_jsonl


def _id(conversation: str, action: str) -> str:
    return "WC-" + hashlib.sha256(f"{conversation}:{action}".encode()).hexdigest()[:24]


def mine_reconstructed(input_path: Path, candidates_path: Path, report_path: Path) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for conversation in iter_jsonl(input_path):
        actions = conversation["actions"]
        by_id = {item["action_id_private"]: item for item in actions}
        for action in actions:
            kind = action["action_type"]
            if kind not in {"MODIFICATION", "DELETION", "RESTORATION"}:
                continue
            parent = str(action.get("parent_id_private") or "")
            prior = by_id.get(parent)
            if prior is None:
                excluded.append({"reason": "SOURCE_INCOMPLETE", "action": action["action_id_private"]})
                continue
            if action.get("lineage_status") != "SUPPORTED":
                excluded.append({"reason": "SOURCE_INCOMPLETE", "action": action["action_id_private"]})
                continue
            if kind == "MODIFICATION" and not action["text_private"].strip():
                excluded.append({"reason": "RESULTING_VALUE_UNRESOLVED", "action": action["action_id_private"]})
                continue
            relation = {"MODIFICATION": "SUPERSEDES", "DELETION": "DELETES", "RESTORATION": "RESTORES"}[kind]
            primary_action = "SUPERSEDE"
            resulting_value = action["text_private"] if kind != "DELETION" else "[DELETED]"
            scope = {"MODIFICATION": "WORDING_STATE", "DELETION": "CONTENT_REMOVAL", "RESTORATION": "DELETION_RESTORATION"}[kind]
            dialogue = [
                {"turn_id": "T001", "role": "editor", "text": prior["text_private"] or "[EMPTY]"},
                {"turn_id": "T002", "role": "editor", "text": action["text_private"] or f"[{kind}]"},
            ]
            item = {
                "schema_version": "1.0",
                "item_id": _id(conversation["conversation_id_private"], action["action_id_private"]),
                "blind_id": None,
                "source_track": "WIKICONV",
                "scope": scope,
                "principal_type": "EDITORIAL_CONTENT_ENTITY",
                "memory_slot": "editorial_content_state",
                "prior_value": prior["text_private"] or "[EMPTY]",
                "candidate_value": resulting_value,
                "dialogue": dialogue,
                "prior_evidence_turn_ids": ["T001"],
                "candidate_turn_id": "T002",
                "context_turn_ids": ["T001", "T002"],
                "constructor_provisional_action": primary_action,
                "constructor_provisional_resulting_value": resulting_value,
                "constructor_rationale": f"Source action {kind} supports provisional relation {relation}.",
                "source_locator_private": {
                    "conversation_id": conversation["conversation_id_private"],
                    "action_id": action["action_id_private"],
                    "parent_id": parent,
                    "page_title": action["page_title_private"],
                    "revision_id": action["revision_id_private"],
                },
                "continuity_keys_private": [
                    f"page:{action['page_title_private'].casefold()}",
                    f"conversation:{conversation['conversation_id_private']}",
                    f"contributor:{action['contributor_private']}",
                    f"lineage:{action.get('ancestor_id_private') or parent}",
                ],
                "privacy_status": "PENDING_HUMAN_REVIEW",
                "construction_status": "CANDIDATE",
                "rejection_reason": None,
            }
            candidates.append(item)
    write_jsonl(candidates_path, candidates, mode=0o600)
    report = {
        "candidates": len(candidates),
        "excluded": len(excluded),
        "scope_counts": dict(Counter(item["scope"] for item in candidates)),
        "rejection_reasons": dict(Counter(item["reason"] for item in excluded)),
        "publication_eligible": False,
    }
    write_json(report_path, report)
    return report

