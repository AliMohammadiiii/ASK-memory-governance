"""Agreement statistics with prevalence, exclusion, and evidence context."""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from statistics import mean
from typing import Any

from mgp_natural.util.io import iter_jsonl, write_json
from mgp_natural.util.text import canonicalize_text

ACTIONS = ("KEEP", "SUPERSEDE", "ABSTAIN")


def cohen_kappa(left: list[str], right: list[str]) -> float:
    """Return Cohen's kappa for two aligned nominal label sequences."""

    if len(left) != len(right) or not left:
        return 0.0
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / len(left)
    lc, rc = Counter(left), Counter(right)
    expected = sum((lc[action] / len(left)) * (rc[action] / len(right)) for action in ACTIONS)
    return 1.0 if expected == 1.0 else (observed - expected) / (1 - expected)


def fleiss_kappa(groups: list[list[str]]) -> float:
    """Return Fleiss' kappa for equally sized, nonempty annotation groups."""

    if not groups:
        return 0.0
    n = len(groups[0])
    if n < 2 or any(len(group) != n for group in groups):
        return 0.0
    p_bar = mean(
        (sum(value * value for value in Counter(group).values()) - n) / (n * (n - 1))
        for group in groups
    )
    total = len(groups) * n
    totals = Counter(action for group in groups for action in group)
    p_e = sum((totals[action] / total) ** 2 for action in ACTIONS)
    return 1.0 if p_e == 1.0 else (p_bar - p_e) / (1 - p_e)


def krippendorff_alpha_nominal(groups: list[list[str]]) -> float:
    """Return nominal Krippendorff's alpha with variable group sizes.

    Excluded or missing labels must be removed before calling this function.
    Groups with fewer than two labels do not contribute observed pairs.
    """

    usable = [group for group in groups if len(group) >= 2]
    if not usable:
        return 0.0
    disagreeing_pairs = 0
    total_pairs = 0
    for group in usable:
        for left, right in combinations(group, 2):
            disagreeing_pairs += int(left != right)
            total_pairs += 1
    observed_disagreement = disagreeing_pairs / total_pairs if total_pairs else 0.0
    totals = Counter(label for group in groups for label in group)
    total_labels = sum(totals.values())
    if total_labels < 2:
        return 0.0
    expected_disagreement = 1.0 - sum((count / total_labels) ** 2 for count in totals.values())
    if expected_disagreement == 0.0:
        return 1.0 if observed_disagreement == 0.0 else 0.0
    return 1.0 - observed_disagreement / expected_disagreement


def _set_overlap(left: list[str], right: list[str]) -> tuple[float, float, float]:
    left_set = set(left)
    right_set = set(right)
    overlap = len(left_set & right_set)
    precision_lr = overlap / len(left_set) if left_set else float(not right_set)
    recall_lr = overlap / len(right_set) if right_set else float(not left_set)
    precision_rl = overlap / len(right_set) if right_set else float(not left_set)
    recall_rl = overlap / len(left_set) if left_set else float(not right_set)
    precision = (precision_lr + precision_rl) / 2
    recall = (recall_lr + recall_rl) / 2
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def _group_summary(groups: list[list[str]]) -> dict[str, Any]:
    exact = [len(set(group)) == 1 for group in groups if group]
    majorities = [max(Counter(group).values()) / len(group) for group in groups if group]
    return {
        "items": len(groups),
        "raw_exact_agreement": mean(exact) if exact else 0.0,
        "mean_majority_agreement": mean(majorities) if majorities else 0.0,
        "action_prevalence": dict(Counter(action for group in groups for action in group)),
    }


def analyze(
    annotations_path: Path,
    output_path: Path | None = None,
    items_path: Path | None = None,
) -> dict[str, Any]:
    """Analyze validated annotation rows.

    The function intentionally reports prevalence and exclusions alongside chance-corrected
    statistics. It does not decide whether agreement is scientifically adequate.
    """

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in iter_jsonl(annotations_path):
        grouped[row["blind_id"]].append(row)

    item_metadata: dict[str, dict[str, str]] = {}
    if items_path is not None:
        for item in iter_jsonl(items_path):
            item_metadata[item["blind_id"]] = {
                "track": str(item.get("source_track", "UNKNOWN")),
                "scope": str(item.get("scope", "UNKNOWN")),
            }

    valid_groups = [
        [row["action"] for row in rows if not row.get("exclude")] for rows in grouped.values()
    ]
    exact = [len(set(group)) == 1 for group in valid_groups if group]
    majorities = [max(Counter(group).values()) / len(group) for group in valid_groups if group]

    annotators = sorted(
        {row["annotator_pseudonym"] for rows in grouped.values() for row in rows}
    )
    pairwise: dict[str, float] = {}
    for left, right in combinations(annotators, 2):
        left_values: list[str] = []
        right_values: list[str] = []
        for rows in grouped.values():
            by_annotator = {
                row["annotator_pseudonym"]: row for row in rows if not row.get("exclude")
            }
            if left in by_annotator and right in by_annotator:
                left_values.append(by_annotator[left]["action"])
                right_values.append(by_annotator[right]["action"])
        if left_values:
            pairwise[f"{left}|{right}"] = cohen_kappa(left_values, right_values)

    evidence_precision: list[float] = []
    evidence_recall: list[float] = []
    evidence_f1: list[float] = []
    resulting_matches: list[bool] = []
    disagreement_pairs: Counter[str] = Counter()
    exclusion_taxonomy: Counter[str] = Counter()

    for rows in grouped.values():
        labeled = [row for row in rows if not row.get("exclude")]
        excluded = [row for row in rows if row.get("exclude")]
        if excluded and labeled:
            exclusion_taxonomy["MIXED_EXCLUSION_AND_LABEL"] += 1
        elif excluded and not labeled:
            exclusion_taxonomy["ALL_EXCLUDED"] += 1
        else:
            exclusion_taxonomy["NO_EXCLUSION"] += 1
        for left, right in combinations(labeled, 2):
            precision, recall, f1 = _set_overlap(
                left["evidence_turn_ids"], right["evidence_turn_ids"]
            )
            evidence_precision.append(precision)
            evidence_recall.append(recall)
            evidence_f1.append(f1)
            if left["action"] != right["action"]:
                disagreement_pairs["|".join(sorted((left["action"], right["action"])))] += 1
            if left["action"] == right["action"] == "SUPERSEDE":
                left_value = canonicalize_text(str(left.get("resulting_value", "")))
                right_value = canonicalize_text(str(right.get("resulting_value", "")))
                resulting_matches.append(left_value == right_value)

    per_class: dict[str, dict[str, Any]] = {}
    for action in ACTIONS:
        shares: list[float] = []
        unanimous = 0
        items_with_any = 0
        for group in valid_groups:
            if not group or action not in group:
                continue
            items_with_any += 1
            share = group.count(action) / len(group)
            shares.append(share)
            unanimous += int(share == 1.0)
        per_class[action] = {
            "annotation_support": sum(group.count(action) for group in valid_groups),
            "items_with_any_support": items_with_any,
            "mean_within_item_label_share": mean(shares) if shares else 0.0,
            "unanimous_item_rate_among_supported": unanimous / items_with_any
            if items_with_any
            else 0.0,
        }

    by_track_scope: dict[str, dict[str, Any]] = {}
    if item_metadata:
        stratified: dict[str, list[list[str]]] = defaultdict(list)
        for blind_id, rows in grouped.items():
            metadata = item_metadata.get(blind_id, {"track": "UNKNOWN", "scope": "UNKNOWN"})
            labels = [row["action"] for row in rows if not row.get("exclude")]
            stratified[f"track={metadata['track']}"] .append(labels)
            stratified[f"track={metadata['track']}|scope={metadata['scope']}"] .append(labels)
        by_track_scope = {key: _group_summary(groups) for key, groups in sorted(stratified.items())}

    all_rows = [row for rows in grouped.values() for row in rows]
    report = {
        "items": len(grouped),
        "raw_exact_agreement": mean(exact) if exact else 0.0,
        "mean_majority_agreement": mean(majorities) if majorities else 0.0,
        "per_class_agreement": per_class,
        "fleiss_kappa_nominal": fleiss_kappa([group for group in valid_groups if group]),
        "krippendorff_alpha_nominal": krippendorff_alpha_nominal(valid_groups),
        "pairwise_cohen_kappa": pairwise,
        "action_prevalence": dict(Counter(action for group in valid_groups for action in group)),
        "confidence_distribution": dict(
            Counter(row["confidence"] for row in all_rows if not row.get("exclude"))
        ),
        "exclusion_rate": sum(row.get("exclude") is True for row in all_rows)
        / max(1, len(all_rows)),
        "disagreement_taxonomy": {
            "action_pair_conflicts": dict(disagreement_pairs),
            "item_exclusion_patterns": dict(exclusion_taxonomy),
        },
        "resulting_value_agreement": {
            "supersede_pairs": len(resulting_matches),
            "canonical_exact_match_rate": mean(resulting_matches) if resulting_matches else None,
        },
        "evidence_span_agreement": {
            "pair_count": len(evidence_f1),
            "mean_pairwise_precision": mean(evidence_precision) if evidence_precision else 0.0,
            "mean_pairwise_recall": mean(evidence_recall) if evidence_recall else 0.0,
            "mean_pairwise_f1": mean(evidence_f1) if evidence_f1 else 0.0,
        },
        "agreement_by_track_and_scope": by_track_scope,
        "interpretation_note": (
            "Chance-corrected agreement must be interpreted with class prevalence, exclusions, "
            "group sizes, and the disagreement taxonomy."
        ),
    }
    if output_path:
        write_json(output_path, report)
    return report

