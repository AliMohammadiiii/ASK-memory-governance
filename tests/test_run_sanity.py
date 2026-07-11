"""Tests for MGP-6 run-level sanity checks."""

from __future__ import annotations

from ksa.eval.sanity import (
    build_sanity_report,
    duplicate_confusion_matrices,
    extraction_recall,
)

_CM = {
    "KEEP": {"KEEP": 5, "SUPERSEDE": 0, "ABSTAIN": 0},
    "SUPERSEDE": {"KEEP": 0, "SUPERSEDE": 3, "ABSTAIN": 0},
    "ABSTAIN": {"KEEP": 0, "SUPERSEDE": 0, "ABSTAIN": 2},
}


def _report(baseline: str, candidate_types: list, confusion=None) -> dict:
    return {
        "baseline": baseline,
        "confusion_matrix": confusion or _CM,
        "predictions": [{"candidate_type": ct, "predicted_action": "KEEP"} for ct in candidate_types],
    }


def test_extraction_recall_none_for_non_updating() -> None:
    assert extraction_recall(_report("no_memory", ["stable_pref"] * 10)) is None


def test_extraction_recall_counts_candidates() -> None:
    report = _report("controller", ["stable_pref", None, "episodic_fact", None])
    assert extraction_recall(report) == 0.5


def test_low_recall_warns() -> None:
    # 2/10 scenarios produced a candidate: the m4w14 bug signature.
    report = _report("controller", ["stable_pref", "stable_pref"] + [None] * 8)
    sanity = build_sanity_report([("controller", report)])
    assert sanity["ok"] is False
    assert any("LOW EXTRACTION RECALL" in w for w in sanity["warnings"])


def test_identical_updating_matrices_warn() -> None:
    reports = [
        ("b4", _report("naive_overwrite", ["stable_pref"] * 10)),
        ("controller", _report("controller", ["stable_pref"] * 10)),
    ]
    assert duplicate_confusion_matrices(reports) == [("b4", "controller")]


def test_non_updating_pair_not_flagged() -> None:
    reports = [
        ("b1", _report("no_memory", ["stable_pref"] * 10)),
        ("b2", _report("flat_vector", ["stable_pref"] * 10)),
    ]
    assert duplicate_confusion_matrices(reports) == []


def test_recency_matching_non_updating_action_matrix_not_flagged() -> None:
    reports = [
        ("b1", _report("no_memory", [None] * 10)),
        ("b3", _report("recency", ["stable_pref"] * 10)),
    ]
    assert duplicate_confusion_matrices(reports) == []


def test_healthy_run_passes() -> None:
    cm_keep = _CM
    cm_diff = {
        "KEEP": {"KEEP": 2, "SUPERSEDE": 1, "ABSTAIN": 0},
        "SUPERSEDE": {"KEEP": 1, "SUPERSEDE": 4, "ABSTAIN": 0},
        "ABSTAIN": {"KEEP": 0, "SUPERSEDE": 0, "ABSTAIN": 2},
    }
    reports = [
        ("b1", _report("no_memory", ["stable_pref"] * 10, cm_keep)),
        ("controller", _report("controller", ["stable_pref"] * 10, cm_diff)),
    ]
    sanity = build_sanity_report(reports)
    assert sanity["ok"] is True
    assert sanity["warnings"] == []
