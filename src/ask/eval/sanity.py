"""Run-level sanity checks that catch silent pipeline bugs in MGP-6 runs.

The runs/m4w14 evaluation looked complete but was invalid: an extraction bug
made 46/60 scenarios produce no candidate, so recency, naive-overwrite, and the
controller all fell through to their "no candidate" branch and produced
byte-identical confusion matrices. These checks turn that exact failure into a
loud, machine-readable warning instead of a result table.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

UPDATING_SYSTEMS = {"recency", "naive_overwrite", "controller"}
# Non-updating baselines always KEEP on MGP-6, so they share a confusion matrix
# by design; an identical matrix among them is expected, not a bug signal.
NON_UPDATING_SYSTEMS = {"no_memory", "flat_vector"}

# Below this fraction of scenarios yielding an extracted candidate, an updating
# system is almost certainly hitting an extraction/parse bug rather than genuine
# "nothing to extract". This is the *bug-signature* floor: a run below it is
# flagged invalid and (with --fail-on-sanity) exits non-zero.
MIN_EXTRACTION_RECALL = 0.5

# Stricter floors required to PROMOTE a run to final thesis numbers (enforced by
# scripts/promote_to_final.py, not by the run itself -- dev runs stay allowed).
# A run at the bug-signature floor (0.5) is "not obviously broken"; a *final*
# run must extract nearly everything. T1 scenarios are explicit "I now prefer X"
# corrections that any competent extractor must catch, so T1 gets its own floor:
# a high overall recall that still drops T1 would hide a systematic miss on the
# exact supersede cases the controller is supposed to handle.
SPEC_MIN_EXTRACTION_RECALL = 0.90
SPEC_MIN_T1_RECALL = 0.90


def extraction_recall(report: Mapping[str, Any]) -> float | None:
    """Fraction of scenarios that produced at least one extracted candidate.

    Only meaningful for updating systems; ``None`` for non-updating baselines
    (no_memory / flat_vector), which never run extraction.
    """
    if report.get("baseline") not in UPDATING_SYSTEMS:
        return None
    predictions = report.get("predictions") or []
    if not predictions:
        return None
    with_candidate = sum(1 for p in predictions if p.get("candidate_type") is not None)
    return with_candidate / len(predictions)


def per_type_extraction_recall(report: Mapping[str, Any]) -> dict[str, float] | None:
    """Extraction recall split by MGP-6 type, parsed from the scenario id.

    Scenario ids are shaped ``MGP6-T<k>-NN``; the type segment is the second
    dash-delimited field. Returns ``None`` for non-updating baselines.
    """
    if report.get("baseline") not in UPDATING_SYSTEMS:
        return None
    predictions = report.get("predictions") or []
    if not predictions:
        return None
    by_type: dict[str, list[int]] = {}
    for p in predictions:
        sid = str(p.get("scenario_id", ""))
        parts = sid.split("-")
        if len(parts) < 2:
            continue
        t = parts[1]
        bucket = by_type.setdefault(t, [0, 0])
        bucket[1] += 1
        if p.get("candidate_type") is not None:
            bucket[0] += 1
    return {t: (got / n if n else 0.0) for t, (got, n) in sorted(by_type.items())}


def action_distribution(report: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in report.get("predictions") or []:
        action = str(p.get("predicted_action"))
        counts[action] = counts.get(action, 0) + 1
    return counts


def duplicate_confusion_matrices(
    reports: list[tuple[str, Mapping[str, Any]]],
) -> list[tuple[str, str]]:
    """Return pairs of system aliases whose confusion matrices are identical."""
    duplicates: list[tuple[str, str]] = []
    for i in range(len(reports)):
        for j in range(i + 1, len(reports)):
            alias_a, report_a = reports[i]
            alias_b, report_b = reports[j]
            both_non_updating = (
                report_a.get("baseline") in NON_UPDATING_SYSTEMS
                and report_b.get("baseline") in NON_UPDATING_SYSTEMS
            )
            recency_vs_non_updating = {
                str(report_a.get("baseline")),
                str(report_b.get("baseline")),
            } <= (NON_UPDATING_SYSTEMS | {"recency"}) and "recency" in {
                str(report_a.get("baseline")),
                str(report_b.get("baseline")),
            }
            if both_non_updating or recency_vs_non_updating:
                continue
            cm_a = json.dumps(report_a.get("confusion_matrix"), sort_keys=True)
            cm_b = json.dumps(report_b.get("confusion_matrix"), sort_keys=True)
            if cm_a == cm_b:
                duplicates.append((alias_a, alias_b))
    return duplicates


def build_sanity_report(reports: list[tuple[str, Mapping[str, Any]]]) -> dict[str, Any]:
    """Assemble warnings and per-system diagnostics for a set of MGP-6 reports."""
    warnings: list[str] = []
    per_system: dict[str, Any] = {}

    for alias, report in reports:
        recall = extraction_recall(report)
        per_type = per_type_extraction_recall(report)
        per_system[alias] = {
            "baseline": report.get("baseline"),
            "extraction_recall": recall,
            "per_type_extraction_recall": per_type,
            "t1_extraction_recall": (per_type or {}).get("T1") if per_type else None,
            "action_distribution": action_distribution(report),
        }
        if recall is not None and recall < MIN_EXTRACTION_RECALL:
            warnings.append(
                f"LOW EXTRACTION RECALL: {alias} ({report.get('baseline')}) produced a "
                f"candidate on only {recall:.0%} of scenarios (< {MIN_EXTRACTION_RECALL:.0%}); "
                "this is the runs/m4w14 extraction-bug signature."
            )

    duplicates = duplicate_confusion_matrices(reports)
    for alias_a, alias_b in duplicates:
        warnings.append(
            f"IDENTICAL CONFUSION MATRIX: {alias_a} and {alias_b} produced byte-identical "
            "confusion matrices; distinct systems should diverge unless there is a real "
            "semantic reason. Verify the pipeline actually ran for both."
        )

    return {
        "ok": not warnings,
        "warnings": warnings,
        "duplicate_confusion_matrices": duplicates,
        "per_system": per_system,
        "thresholds": {
            "min_extraction_recall": MIN_EXTRACTION_RECALL,
            "spec_min_extraction_recall": SPEC_MIN_EXTRACTION_RECALL,
            "spec_min_t1_recall": SPEC_MIN_T1_RECALL,
        },
    }
