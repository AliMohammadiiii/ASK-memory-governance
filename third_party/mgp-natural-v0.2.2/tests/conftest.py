from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture
def blind_items() -> list[dict[str, Any]]:
    return load_jsonl(FIXTURES / "blind_items.jsonl")


@pytest.fixture
def annotations() -> list[dict[str, Any]]:
    return load_jsonl(FIXTURES / "annotations_valid.jsonl")


@pytest.fixture
def adjudications() -> list[dict[str, Any]]:
    return load_jsonl(FIXTURES / "adjudications_valid.jsonl")


@pytest.fixture
def construction_item() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "item_id": "item-1",
        "blind_id": None,
        "source_track": "STUDYCHAT",
        "scope": "CORRECTION_STATE",
        "principal_type": "PSEUDONYMOUS_USER",
        "memory_slot": "active_dataset_file",
        "prior_value": "old.csv",
        "candidate_value": "new.csv",
        "dialogue": [
            {"turn_id": "T001", "role": "user", "text": "Use old.csv."},
            {"turn_id": "T002", "role": "assistant", "text": "Okay."},
            {"turn_id": "T003", "role": "user", "text": "Actually use new.csv instead."},
        ],
        "prior_evidence_turn_ids": ["T001"],
        "candidate_turn_id": "T003",
        "context_turn_ids": ["T001", "T002", "T003"],
        "constructor_provisional_action": "SUPERSEDE",
        "constructor_provisional_resulting_value": "new.csv",
        "constructor_rationale": "Synthetic test only.",
        "lineage_relation_private": "SUPERSEDES",
        "stage1_signals": ["EXPLICIT_UPDATE", "FILE_REFERENCE"],
        "source_locator_private": {"user": "private-user", "chat": "private-chat"},
        "continuity_keys_private": ["user:private-user", "chat:private-chat"],
        "privacy_status": "PENDING_HUMAN_REVIEW",
        "construction_status": "CANDIDATE",
        "rejection_reason": None,
    }


@pytest.fixture
def clone() -> Any:
    return copy.deepcopy

