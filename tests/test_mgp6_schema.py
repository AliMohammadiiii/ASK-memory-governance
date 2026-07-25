"""MGP-6 scenario schema and coverage tests."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from ask.eval.mgp6_schema import load_mgp6_jsonl, validate_mgp6_coverage


def test_mgp6_v1_schema_and_coverage() -> None:
    path = Path("data/mgp6_v1_seed0.jsonl")
    scenarios = load_mgp6_jsonl(path)
    validate_mgp6_coverage(scenarios)

    assert Counter(s.type for s in scenarios) == {
        "T1": 10,
        "T2": 10,
        "T3": 10,
        "T4": 10,
        "T5": 10,
        "T6": 10,
    }
    assert {s.gold_action for s in scenarios} == {"KEEP", "SUPERSEDE", "ABSTAIN"}
