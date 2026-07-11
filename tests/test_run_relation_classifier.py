"""Tests for relation-classifier runner row conversion helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_relation_classifier.py"
_SPEC = importlib.util.spec_from_file_location("run_relation_classifier", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
run_relation_classifier = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run_relation_classifier)


def test_prior_from_row_prefers_embedded_prior_memory() -> None:
    row = {
        "gold_label": {"type": "stable_pref"},
        "prior_memory": {
            "text": "User avoids coffee in the morning.",
            "type": "stable_pref",
            "memory_id": "prior-1",
            "timestamp": "2024-01-01T00:00:00Z",
        },
    }

    prior = run_relation_classifier._prior_from_row(row, "User prefers coffee.")

    assert prior.text == "User avoids coffee in the morning."
    assert prior.memory_id == "prior-1"
    assert prior.timestamp == "2024-01-01T00:00:00Z"


def test_prior_from_row_keeps_synthetic_fallback() -> None:
    row = {"gold_label": {"type": "stable_pref"}}

    prior = run_relation_classifier._prior_from_row(row, "User prefers coffee.")

    assert prior.text == "User prefers coffee."
    assert prior.memory_id == "canonical-coffee-prior"
