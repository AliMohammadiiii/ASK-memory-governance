"""Tests for the research-backed relation-dev builder."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_relation_dev100_from_research.py"
_SPEC = importlib.util.spec_from_file_location("build_relation_dev100_from_research", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
builder = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(builder)


def test_dialogue_nli_preference_type_mapping() -> None:
    row = {
        "sentence1": "i really do not like meat .",
        "sentence2": "i do not eat meat .",
        "triple1": ["i", "dislike", "meat"],
    }

    assert builder._dialogue_memory_type(row) == "stable_pref"


def test_dialogue_nli_fact_type_mapping() -> None:
    row = {
        "sentence1": "i work as a librarian .",
        "sentence2": "i work as a teacher .",
        "triple1": ["i", "has_profession", "librarian"],
    }

    assert builder._dialogue_memory_type(row) == "episodic_fact"


def test_alps_preference_type_mapping() -> None:
    memory = {
        "label": "Preferences/Entertainment",
        "preference_attitude": "create",
        "value": "Currently wants a realistic animal story.",
    }

    assert builder._alps_memory_type(memory) == "stable_pref"


def test_english_filter_rejects_non_latin_rows() -> None:
    assert builder._looks_english("Currently prefers coffee over tea.")
    assert not builder._looks_english("公司命名时不再硬性排除")
