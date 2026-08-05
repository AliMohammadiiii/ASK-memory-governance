"""WikiConv action and lineage reconstruction."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from mgp_natural.errors import ValidationError
from mgp_natural.util.io import iter_jsonl, write_jsonl

ACTION_TYPES = {"CREATION", "ADDITION", "MODIFICATION", "DELETION", "RESTORATION"}


def normalize_action(row: dict[str, Any]) -> dict[str, Any]:
    required = {"id", "conversation_id", "page_title", "type", "timestamp"}
    missing = required - set(row)
    if missing:
        raise ValidationError(f"WikiConv action missing: {sorted(missing)}")
    if row["type"] not in ACTION_TYPES:
        raise ValidationError(f"unknown WikiConv action: {row['type']}")
    if row["type"] in {"MODIFICATION", "DELETION", "RESTORATION"} and not row.get("parent_id"):
        raise ValidationError(f"{row['type']} requires parent_id")
    return {
        "action_id_private": str(row["id"]),
        "conversation_id_private": str(row["conversation_id"]),
        "page_title_private": str(row["page_title"]),
        "page_id_private": str(row.get("page_id", "")),
        "section_private": str(row.get("section", "")),
        "contributor_private": str(row.get("user_id") or row.get("user_text") or "UNKNOWN"),
        "revision_id_private": str(row.get("rev_id", "")),
        "reply_to_private": row.get("replyTo_id") or row.get("reply_to"),
        "parent_id_private": row.get("parent_id"),
        "ancestor_id_private": row.get("ancestor_id"),
        "timestamp_private": row["timestamp"],
        "action_type": row["type"],
        "text_private": row.get("cleaned_content") or row.get("content") or row.get("text") or "",
    }


def reconstruct_actions(input_path: Path, output_path: Path) -> dict[str, int]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_ids: set[str] = set()
    for raw in iter_jsonl(input_path):
        action = normalize_action(raw)
        action_id = action["action_id_private"]
        if action_id in seen_ids:
            raise ValidationError(f"duplicate WikiConv action id: {action_id}")
        seen_ids.add(action_id)
        groups[action["conversation_id_private"]].append(action)
    output = []
    for conversation_id, actions in sorted(groups.items()):
        actions.sort(key=lambda item: (str(item["timestamp_private"]), item["action_id_private"]))
        available: set[str] = set()
        for action in actions:
            parent = action["parent_id_private"]
            if parent and str(parent) not in available:
                action["lineage_status"] = "PARENT_OUTSIDE_EXTRACT_OR_ORDER_CONFLICT"
            else:
                action["lineage_status"] = "SUPPORTED"
            available.add(action["action_id_private"])
        output.append(
            {
                "schema_version": "1.0",
                "source_track": "WIKICONV",
                "conversation_id_private": conversation_id,
                "actions": actions,
            }
        )
    write_jsonl(output_path, output, mode=0o600)
    return {
        "conversations": len(output),
        "actions": sum(len(item["actions"]) for item in output),
    }

