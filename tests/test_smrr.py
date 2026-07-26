"""SMRR fixture tests."""

from __future__ import annotations

from ask.eval.mgp6_schema import load_mgp6_jsonl
from ask.eval.smrr import compute_smrr, mgp6_stale_items


def test_compute_smrr_counts_retrieved_superseded_memory() -> None:
    result = compute_smrr(
        retrieved_items=[
            {"text": "User prefers coffee in the morning."},
            {"text": "User prefers green tea in the morning."},
        ],
        stale_items=[{"text": "user prefers coffee in the morning"}],
    )

    assert result.stale_retrieval_count == 1
    assert result.smrr_denominator == 2
    assert result.smrr == 0.5
    assert result.to_dict()["smrr_status"] == "computed"


def test_mgp6_stale_items_uses_gold_supersession_state() -> None:
    scenario = {row.scenario_id: row for row in load_mgp6_jsonl("data/mgp6_v1_seed0.jsonl")}[
        "MGP6-T1-01"
    ]

    stale = mgp6_stale_items(scenario)

    assert stale
    assert stale[0]["id"] == scenario.initial_memory_state[0].id
