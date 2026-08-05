from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

from mgp_natural.util.io import canonical_json_hash, iter_jsonl, write_json, write_jsonl
from mgp_natural.util.text import canonicalize_text

ACTIONS = ("KEEP", "SUPERSEDE", "ABSTAIN")
PASS_CONFIGS = (
    ("AI_OFFLINE_RULE_PASS_01", 1729),
    ("AI_OFFLINE_RULE_PASS_02", 1730),
    ("AI_OFFLINE_RULE_PASS_03", 1731),
)
UNCERTAINTY = re.compile(
    r"(?i)\b(?:maybe|perhaps|not\s+sure|uncertain|might|could|considering|possibly)\b"
)
UPDATE = re.compile(
    r"(?i)\b(?:actually|instead|rather\s+than|from\s+now\s+on|no\s+longer|"
    r"i\s+meant|switch(?:ing)?\s+to|replace|revert|rollback|remove|delete|restore)\b"
)
REAFFIRM = re.compile(r"(?i)\b(?:continue|keep|still|same|as\s+before|exactly|yes)\b")
PROMPT_VERSION = "mgp-natural-offline-ai-provisional-v1"
PROMPT_TEXT = (
    "Judge one blind write-time memory-governance item as KEEP, SUPERSEDE, ABSTAIN, "
    "or EXCLUDE using only the prior value, scope, dialogue, and candidate marker. "
    "Return concise evidence-based fields. This offline replay is provisional, not gold."
)


def _timestamp() -> str:
    return os.environ.get("MGP_RUN_TIMESTAMP", "2026-08-04T00:00:00Z")


def _candidate_text(item: dict[str, Any]) -> str:
    candidate_id = item["candidate_turn_id"]
    for turn in item["dialogue"]:
        if turn["turn_id"] == candidate_id:
            return str(turn["text"])
    return ""


def _evidence_ids(item: dict[str, Any]) -> list[str]:
    ids = [str(turn["turn_id"]) for turn in item["dialogue"]]
    candidate = str(item["candidate_turn_id"])
    evidence = [ids[0]] if ids and ids[0] != candidate else []
    evidence.append(candidate)
    return evidence


def _judge(item: dict[str, Any], pass_index: int) -> dict[str, Any]:
    prior = str(item["prior_value"])
    candidate = _candidate_text(item).strip()
    scope = str(item["scope"])
    exclude = False
    exclusion_reason: str | None = None
    ambiguity: str | None = None
    if not candidate:
        exclude = True
        exclusion_reason = "INSUFFICIENT_CONTEXT"
        action = None
        confidence = 1
        resulting: str | None = None
        relation: str | None = None
        rationale = "The marked candidate turn is absent or empty in the blind item."
    elif UNCERTAINTY.search(candidate):
        action = "ABSTAIN"
        confidence = 4 if pass_index != 1 else 3
        resulting = prior
        relation = "WITHHOLDS_COMMITMENT"
        ambiguity = "UNCERTAINTY_OR_CONDITIONALITY"
        rationale = "The candidate expresses uncertainty rather than a committed state update."
    elif scope == "CONTENT_REMOVAL" or "CONTENT REMOVED" in candidate.upper():
        action = "SUPERSEDE"
        confidence = 4
        resulting = "[DELETED]"
        relation = "DELETES"
        rationale = "The released context represents removal of the prior standing content."
    elif scope == "DELETION_RESTORATION":
        action = "SUPERSEDE"
        confidence = 4
        resulting = candidate
        relation = "RESTORES"
        rationale = "The candidate restores a later standing content value."
    elif canonicalize_text(candidate) == canonicalize_text(prior) or REAFFIRM.search(candidate):
        action = "KEEP"
        confidence = 4 if canonicalize_text(candidate) == canonicalize_text(prior) else 3
        resulting = prior
        relation = "REAFFIRMS"
        rationale = "The candidate reaffirms or remains compatible with the prior standing value."
    elif UPDATE.search(candidate) or scope in {"WORDING_STATE", "CORRECTION_STATE"}:
        action = "SUPERSEDE"
        confidence = 4 if UPDATE.search(candidate) else 3
        resulting = candidate
        relation = "SUPERSEDES"
        rationale = "The candidate supplies a later replacement value for the same visible slot."
    else:
        action = "ABSTAIN"
        confidence = 2 if pass_index != 2 else 1
        resulting = prior
        relation = "WITHHOLDS_COMMITMENT"
        ambiguity = "INSUFFICIENT_EXPLICIT_COMMITMENT"
        rationale = "The blind context does not make a safe state write sufficiently explicit."
    return {
        "exclude": exclude,
        "exclusion_reason": exclusion_reason,
        "action": action,
        "confidence": confidence,
        "evidence_turn_ids": _evidence_ids(item),
        "resulting_value": resulting,
        "rationale": rationale,
        "ambiguity_category": ambiguity,
        "lineage_relation": relation,
    }


def _provenance(
    *,
    item: dict[str, Any],
    annotator_id: str,
    seed: int,
    run_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "protocol_version": PROMPT_VERSION,
        "blind_id": item["blind_id"],
        "ai_tag": "AI",
        "annotation_status": "AI_PROVISIONAL_NOT_GOLD",
        "annotator_type": "AI",
        "annotator_id": annotator_id,
        "model_family": "deterministic-offline-provisional-controller",
        "reasoning_mode": "rule_mediated_offline_replay",
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(PROMPT_TEXT.encode()).hexdigest(),
        "run_id": run_id,
        "generated_at_utc": _timestamp(),
        "human_verified": False,
        "requires_human_review": True,
        "pass_seed": seed,
        "item_sha256": canonical_json_hash(item),
    }


def _validate_row(row: dict[str, Any]) -> None:
    if row["annotation_status"] != "AI_PROVISIONAL_NOT_GOLD":
        raise ValueError("AI pass row has invalid status")
    if row["human_verified"] is not False or row["requires_human_review"] is not True:
        raise ValueError("AI pass row must remain unverified and review-required")
    if row["exclude"]:
        if row["action"] is not None or not row["exclusion_reason"]:
            raise ValueError("excluded AI row must omit action and state an exclusion reason")
        return
    if row["action"] not in ACTIONS:
        raise ValueError("invalid AI action")
    if row["confidence"] not in range(1, 6):
        raise ValueError("invalid AI confidence")
    if row["action"] == "SUPERSEDE" and not str(row["resulting_value"] or "").strip():
        raise ValueError("AI SUPERSEDE row requires a resulting value")


def _action_key(row: dict[str, Any]) -> str:
    return "EXCLUDE" if row["exclude"] else str(row["action"])


def _majority(values: list[str]) -> str:
    counts = Counter(values)
    return sorted(counts, key=lambda value: (-counts[value], value))[0]


def _consensus_row(
    item: dict[str, Any],
    pass_rows: list[dict[str, Any]],
    run_id: str,
) -> dict[str, Any]:
    action_values = [_action_key(row) for row in pass_rows]
    winning = _majority(action_values)
    agreeing = [row for row in pass_rows if _action_key(row) == winning]
    evidence = sorted(
        set.intersection(*(set(row["evidence_turn_ids"]) for row in agreeing))
        if agreeing
        else set()
    )
    if item["candidate_turn_id"] not in evidence:
        evidence.append(item["candidate_turn_id"])
    result_values = [str(row["resulting_value"] or "") for row in agreeing]
    resulting = _majority(result_values) if result_values else None
    excluded = winning == "EXCLUDE"
    return {
        "schema_version": "1.0",
        "protocol_version": PROMPT_VERSION,
        "blind_id": item["blind_id"],
        "ai_tag": "AI",
        "annotation_status": "AI_ADJUDICATED_PROVISIONAL_NOT_GOLD",
        "annotator_type": "AI",
        "annotator_id": "AI_OFFLINE_RULE_CONSENSUS",
        "model_family": "deterministic-offline-provisional-controller",
        "reasoning_mode": "majority_consensus_over_three_offline_passes",
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(PROMPT_TEXT.encode()).hexdigest(),
        "run_id": run_id,
        "generated_at_utc": _timestamp(),
        "human_verified": False,
        "requires_human_review": True,
        "source_pass_ids": [row["annotator_id"] for row in pass_rows],
        "source_pass_sha256": [canonical_json_hash(row) for row in pass_rows],
        "exclude": excluded,
        "exclusion_reason": (
            _majority([str(row["exclusion_reason"]) for row in agreeing])
            if excluded
            else None
        ),
        "action": None if excluded else winning,
        "confidence": min(int(row["confidence"]) for row in agreeing),
        "evidence_turn_ids": evidence,
        "resulting_value": None if excluded else resulting,
        "rationale": (
            "Offline provisional consensus from three blind deterministic passes; "
            "not independent human adjudication and not gold."
        ),
        "ambiguity_category": (
            None
            if len(set(action_values)) == 1
            else "AI_PASS_ACTION_DISAGREEMENT"
        ),
        "lineage_relation": _majority(
            [str(row["lineage_relation"] or "") for row in agreeing]
        ),
        "action_votes": dict(Counter(action_values)),
        "item_sha256": canonical_json_hash(item),
    }


def annotate(repo_root: Path) -> dict[str, Any]:
    private = repo_root / ".private" / "full"
    items_path = private / "packets" / "combined" / "bundle" / "items.jsonl"
    if not items_path.is_file():
        raise FileNotFoundError("run make full-privacy-blind before AI provisional annotation")
    items = list(iter_jsonl(items_path))
    output_dir = repo_root / "data" / "derived" / "ai_provisional"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = "full-natural-20260804-offline-provisional-v1"
    rows_by_pass: list[dict[str, dict[str, Any]]] = []
    for pass_index, (annotator_id, seed) in enumerate(PASS_CONFIGS):
        order = list(items)
        random.Random(seed).shuffle(order)
        rows: list[dict[str, Any]] = []
        by_id: dict[str, dict[str, Any]] = {}
        for item in order:
            row = {
                **_provenance(
                    item=item,
                    annotator_id=annotator_id,
                    seed=seed,
                    run_id=run_id,
                ),
                **_judge(item, pass_index),
            }
            _validate_row(row)
            rows.append(row)
            by_id[str(row["blind_id"])] = row
        write_jsonl(
            output_dir / f"annotations.pass{pass_index + 1:02d}.ai_provisional.jsonl",
            rows,
        )
        rows_by_pass.append(by_id)
    consensus: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    human_priority: list[dict[str, Any]] = []
    exact_agreement = 0
    action_agreement = 0
    evidence_jaccards: list[float] = []
    resulting_agreement = 0
    for item in items:
        blind_id = str(item["blind_id"])
        pass_rows = [rows[blind_id] for rows in rows_by_pass]
        action_keys = [_action_key(row) for row in pass_rows]
        if len(set(action_keys)) == 1:
            action_agreement += 1
        result_values = [str(row["resulting_value"] or "") for row in pass_rows]
        if len(set(result_values)) == 1:
            resulting_agreement += 1
        evidence_sets = [set(row["evidence_turn_ids"]) for row in pass_rows]
        pair_scores = []
        for left, right in ((0, 1), (0, 2), (1, 2)):
            union = evidence_sets[left] | evidence_sets[right]
            pair_scores.append(
                len(evidence_sets[left] & evidence_sets[right]) / max(1, len(union))
            )
        evidence_jaccards.append(sum(pair_scores) / len(pair_scores))
        comparable = [
            {
                key: row[key]
                for key in (
                    "exclude",
                    "exclusion_reason",
                    "action",
                    "confidence",
                    "evidence_turn_ids",
                    "resulting_value",
                    "ambiguity_category",
                    "lineage_relation",
                )
            }
            for row in pass_rows
        ]
        if len({canonical_json_hash(row) for row in comparable}) == 1:
            exact_agreement += 1
        consensus_row = _consensus_row(item, pass_rows, run_id)
        consensus.append(consensus_row)
        reasons = []
        if len(set(action_keys)) > 1:
            reasons.append("ACTION_DISAGREEMENT")
        if any(row["exclude"] for row in pass_rows):
            reasons.append("ANY_PASS_EXCLUDE")
        if min(int(row["confidence"]) for row in pass_rows) <= 2:
            reasons.append("LOW_CONFIDENCE")
        if len(set(result_values)) > 1:
            reasons.append("RESULTING_VALUE_DISAGREEMENT")
        if min(pair_scores) < 0.5:
            reasons.append("EVIDENCE_SPAN_DISAGREEMENT")
        if item["scope"] in {
            "CONTENT_REMOVAL",
            "DELETION_RESTORATION",
            "CROSS_SESSION_USER_PREFERENCE",
        }:
            reasons.append("MANDATORY_HIGH_RISK_SLICE")
        if reasons:
            disagreements.append(
                {
                    "blind_id": blind_id,
                    "action_votes": dict(Counter(action_keys)),
                    "review_reasons": sorted(set(reasons)),
                }
            )
            human_priority.append(
                {
                    "blind_id": blind_id,
                    "source_track": item["source_track"],
                    "scope": item["scope"],
                    "priority_reasons": ";".join(sorted(set(reasons))),
                    "review_status": "PENDING_HUMAN_REVIEW",
                }
            )
    write_jsonl(output_dir / "consensus.ai_provisional.jsonl", consensus)
    report = {
        "schema_version": "1.0",
        "items": len(items),
        "passes": 3,
        "same_model_or_controller_passes": True,
        "independent_human_annotation": False,
        "human_gold": False,
        "exact_full_row_agreement": exact_agreement / max(1, len(items)),
        "action_agreement": action_agreement / max(1, len(items)),
        "mean_pairwise_evidence_jaccard": sum(evidence_jaccards)
        / max(1, len(evidence_jaccards)),
        "resulting_value_agreement": resulting_agreement / max(1, len(items)),
        "disagreement_items": len(disagreements),
        "consensus_action_distribution_provisional_only": dict(
            Counter(_action_key(row) for row in consensus)
        ),
        "model_family": "deterministic-offline-provisional-controller",
        "publication_eligible": False,
    }
    write_json(repo_root / "reports" / "AI_ANNOTATION_AGREEMENT.json", report)
    disagreement_path = repo_root / "reports" / "AI_ANNOTATION_DISAGREEMENTS.csv"
    with disagreement_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv_writer(handle, ["blind_id", "action_votes", "review_reasons"])
        writer.writeheader()
        for row in disagreements:
            writer.writerow(
                {
                    "blind_id": row["blind_id"],
                    "action_votes": json.dumps(row["action_votes"], sort_keys=True),
                    "review_reasons": ";".join(row["review_reasons"]),
                }
            )
    priority_path = repo_root / "reports" / "HUMAN_ANNOTATION_PRIORITY_QUEUE.csv"
    with priority_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv_writer(
            handle,
            [
                "blind_id",
                "source_track",
                "scope",
                "priority_reasons",
                "review_status",
            ],
        )
        writer.writeheader()
        writer.writerows(human_priority)
    return report


def csv_writer(handle: Any, fieldnames: list[str]) -> Any:
    import csv

    return csv.DictWriter(handle, fieldnames=fieldnames)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate offline AI-provisional blind passes")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(json.dumps(annotate(args.repo_root.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()

