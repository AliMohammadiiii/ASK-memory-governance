"""Gold creation after explicit human authorization and validated adjudication."""
from __future__ import annotations

from pathlib import Path

from mgp_natural.errors import GateBlockedError, ValidationError
from mgp_natural.util.io import iter_jsonl, read_json, write_jsonl

REQUIRED_APPROVALS = {
    "legal_and_redistribution",
    "manual_privacy_review",
    "independent_annotation",
    "independent_adjudication",
    "mapping_reveal_authorization",
    "split_audit",
    "release_decision",
}


def _approved(approvals_path: Path) -> None:
    approvals = read_json(approvals_path)
    recorded = {
        key
        for key, value in approvals.get("human_approvals", {}).items()
        if value.get("status") == "APPROVED_BY_RECORDED_HUMAN" and value.get("approver")
    }
    missing = REQUIRED_APPROVALS - recorded
    if missing:
        raise GateBlockedError(f"gold creation blocked; missing recorded approvals: {sorted(missing)}")


def build_gold(
    items_path: Path,
    adjudications_path: Path,
    approvals_path: Path,
    output_path: Path,
) -> int:
    _approved(approvals_path)
    items = {row["blind_id"]: row for row in iter_jsonl(items_path)}
    rows = []
    for adjudication in iter_jsonl(adjudications_path):
        blind_id = adjudication["blind_id"]
        if blind_id not in items:
            raise ValidationError("adjudication references unknown item")
        if adjudication.get("final_exclude"):
            continue
        rows.append(
            {
                "schema_version": "1.0",
                "blind_id": blind_id,
                "source_track": items[blind_id]["source_track"],
                "scope": items[blind_id]["scope"],
                "action": adjudication["final_action"],
                "evidence_turn_ids": adjudication["final_evidence_turn_ids"],
                "resulting_value": adjudication.get("final_resulting_value") or items[blind_id]["prior_value"],
                "annotation_status": "independently_adjudicated_gold",
            }
        )
    if not rows:
        raise ValidationError("gold would be empty")
    write_jsonl(output_path, rows, mode=0o600)
    return len(rows)

