"""Tests for the H2 superseded-memory recoverability metric."""

from __future__ import annotations

from ask.eval.recoverability import (
    aggregate_recoverability,
    recoverability_for_scenario,
)

# Real shapes pulled from runs/m4w14 predictions.jsonl (T2 supersede scenarios).
CONTROLLER_STATE = [
    {"id": "m0", "status": "superseded", "supersedes_id": None, "type": "stable_pref"},
    {"id": "p1", "status": "active", "supersedes_id": "m0", "type": "stable_pref"},
]
OVERWRITE_STATE = [
    {"id": "p1", "status": "active", "supersedes_id": None, "type": "stable_pref"},
]
KEPT_STATE = [
    {"id": "m0", "status": "active", "supersedes_id": None, "type": "stable_pref"},
]


def test_controller_supersede_is_recoverable() -> None:
    result = recoverability_for_scenario("m0", CONTROLLER_STATE)
    assert result.revision_occurred is True
    assert result.superseded_record_present is True
    assert result.lineage_edge_present is True
    assert result.recoverable is True


def test_naive_overwrite_is_not_recoverable() -> None:
    result = recoverability_for_scenario("m0", OVERWRITE_STATE)
    assert result.revision_occurred is True
    assert result.superseded_record_present is False
    assert result.lineage_edge_present is False
    assert result.recoverable is False


def test_keep_is_not_a_revision() -> None:
    result = recoverability_for_scenario("m0", KEPT_STATE)
    assert result.revision_occurred is False
    assert result.recoverable is False


def test_aggregate_separates_controller_from_overwrite() -> None:
    controller = aggregate_recoverability(
        [recoverability_for_scenario("m0", CONTROLLER_STATE) for _ in range(9)]
    )
    overwrite = aggregate_recoverability(
        [recoverability_for_scenario("m0", OVERWRITE_STATE) for _ in range(9)]
    )
    assert controller["superseded_recoverability"] == 1.0
    assert overwrite["superseded_recoverability"] == 0.0


def test_aggregate_excludes_non_revisions_from_denominator() -> None:
    mixed = aggregate_recoverability(
        [
            recoverability_for_scenario("m0", CONTROLLER_STATE),
            recoverability_for_scenario("m0", KEPT_STATE),
        ]
    )
    assert mixed["n_revisions"] == 1
    assert mixed["superseded_recoverability"] == 1.0


def test_no_revisions_gives_none() -> None:
    summary = aggregate_recoverability([recoverability_for_scenario("m0", KEPT_STATE)])
    assert summary["n_revisions"] == 0
    assert summary["superseded_recoverability"] is None
