from __future__ import annotations

from benchmarks.mgp6 import metrics_mgp6 as m


def test_action_aliases_are_canonicalized() -> None:
    assert m.canonical_action("superseded") == "SUPERSEDE"
    assert m.canonical_action("no-op") == "ABSTAIN"
    assert m.canonical_action(" kept ") == "KEEP"


def test_memory_values_are_canonicalized_symmetrically() -> None:
    a = [
        {
            "semantic_slot": "drink",
            "type": "stable_pref",
            "text": "drink = Green-Tea",
            "status": "active",
        }
    ]
    b = [
        {
            "semantic_slot": "drink",
            "type": "stable_pref",
            "text": "green_tea",
            "status": "active",
        }
    ]
    assert m.active_signature(a) == m.active_signature(b)
