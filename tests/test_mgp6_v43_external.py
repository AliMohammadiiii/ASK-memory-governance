"""Unit tests for public-only external-memory evaluation plumbing."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ask.eval.mgp6_v43 import (
    PROHIBITED_MODEL_KEYS,
    load_predictions_allow_partial,
    load_public_records,
)
from ask.eval.mgp6_v43_external import (
    EXTERNAL_DERIVATION_VERSION,
    backend_seed_payload,
    derive_external_action,
    run_external_record,
)
from scripts.run_mgp6_v43_external import (
    REPO_ROOT,
    _existing_prediction_ids,
    _is_fatal_provider_error,
    select_shard_records,
)
from scripts.run_mgp6_v43_external_sharded import merge_shards

ROOT = Path(__file__).resolve().parents[1]


class _Observation:
    replaced_old = False
    committed_new = True
    raw = {"implementation": "test"}


class _Backend:
    name = "fake"

    def __init__(self) -> None:
        self.namespace = ""
        self.seed_records: list[dict[str, Any]] = []
        self.writes: list[str] = []

    def reset(self, scenario_id: str) -> None:
        self.namespace = scenario_id

    def seed(self, records: list[dict[str, Any]], dialogue: list[dict[str, str]]) -> None:
        self.seed_records = records
        assert dialogue == []

    def write(self, text: str) -> _Observation:
        self.writes.append(text)
        return _Observation()

    def snapshot(self) -> list[str]:
        return ["Stored memory: Example's preference is new value."]

    def search(self, query: str, k: int = 5) -> list[str]:
        return [f"retrieved for {query}"][:k]

    def close(self) -> None:
        pass

    def meta(self) -> dict[str, Any]:
        return {}


def _record_with_requested_value(tmp_path: Path):
    raw = {
        "public_id": "MGP43-0123456789ABCDEF0123",
        "memory_before": {
            "memory_slot": "preference",
            "principal": "Example",
            "standing_value": "old value",
        },
        "dialogue": [
            {"speaker": "USER", "text": "Example changed a preference."},
            {"speaker": "ASSISTANT", "text": "What is the new preference?"},
            {"speaker": "USER", "text": "The requested value is new value."},
        ],
        "evaluation_query": "What should happen?",
        "gold_action": "SUPERSEDE",
    }
    source = tmp_path / "external_record.jsonl"
    source.write_text(json.dumps(raw) + "\n", encoding="utf-8")
    return load_public_records(source)[0]


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_keys(child) for child in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(child) for child in value)) if value else set()
    return set()


def test_external_seed_payload_is_model_safe_and_label_free(tmp_path: Path) -> None:
    record = _record_with_requested_value(tmp_path)
    records, dialogue = backend_seed_payload(record)
    assert records[0]["text"].endswith("old value.")
    assert [turn["role"] for turn in dialogue] == ["user", "assistant", "user"]
    assert not (_keys({"records": records, "dialogue": dialogue}) & PROHIBITED_MODEL_KEYS)


def test_external_state_mapping_is_explicit_about_ambiguity() -> None:
    assert (
        derive_external_action(prior_value="old", candidate_value="new", post_texts=["new"]).action
        == "SUPERSEDE"
    )
    assert (
        derive_external_action(prior_value="old", candidate_value="new", post_texts=["old"]).action
        == "KEEP"
    )
    ambiguous = derive_external_action(
        prior_value="old", candidate_value="new", post_texts=["old and new"]
    )
    assert ambiguous.action == "ABSTAIN"
    assert ambiguous.state_classification == "dual_active_ambiguous"


def test_external_record_uses_public_namespace_and_never_observes_gold(tmp_path: Path) -> None:
    backend = _Backend()
    result = run_external_record(backend, _record_with_requested_value(tmp_path))
    assert backend.namespace == "mgp6-v43:MGP43-0123456789ABCDEF0123"
    assert len(backend.writes) == 3
    assert result["derived_action"] == "SUPERSEDE"
    assert result["derivation_version"] == EXTERNAL_DERIVATION_VERSION
    assert "gold_action" not in result
    assert not (_keys(result) & PROHIBITED_MODEL_KEYS)


def test_external_runner_treats_a_fresh_prediction_path_as_empty(tmp_path: Path) -> None:
    assert _existing_prediction_ids(tmp_path / "predictions.jsonl") == set()


def test_external_runner_adds_repository_root_for_adapter_imports() -> None:
    assert str(REPO_ROOT) in sys.path


def test_external_runner_shards_are_deterministic_and_disjoint() -> None:
    records = [
        SimpleNamespace(public_id=value) for value in ("MGP43-C", "MGP43-A", "MGP43-D", "MGP43-B")
    ]
    shards = [select_shard_records(records, shard_count=3, shard_index=index) for index in range(3)]
    assert [[record.public_id for record in shard] for shard in shards] == [
        ["MGP43-A", "MGP43-D"],
        ["MGP43-B"],
        ["MGP43-C"],
    ]
    assert {record.public_id for shard in shards for record in shard} == {
        "MGP43-A",
        "MGP43-B",
        "MGP43-C",
        "MGP43-D",
    }


def test_external_runner_stops_on_insufficient_provider_credits() -> None:
    assert _is_fatal_provider_error(RuntimeError("Error code: 402 - Insufficient credits"))
    assert not _is_fatal_provider_error(RuntimeError("Connection error"))


def test_external_shard_merge_requires_and_publishes_exact_coverage(tmp_path: Path) -> None:
    source_rows = (
        (ROOT / "benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[:3]
    )
    input_path = tmp_path / "public.jsonl"
    input_path.write_text("\n".join(source_rows) + "\n", encoding="utf-8")
    records = load_public_records(input_path, require_gold=False)
    shards_root = tmp_path / "_shards"
    for index in range(2):
        shard = shards_root / f"shard-{index:02d}"
        shard.mkdir(parents=True)
        selected = select_shard_records(records, shard_count=2, shard_index=index)
        (shard / "predictions.jsonl").write_text(
            "".join(
                json.dumps({"public_id": record.public_id, "action": "KEEP"}) + "\n"
                for record in selected
            ),
            encoding="utf-8",
        )
        (shard / "external_observations.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "public_id": record.public_id,
                        "derived_action": "KEEP",
                        "native_writes": [],
                    }
                )
                + "\n"
                for record in selected
            ),
            encoding="utf-8",
        )
    out = tmp_path / "merged"
    out.mkdir()
    merge_shards(input_path=input_path, shards_root=shards_root, out=out, shard_count=2)
    assert [
        row.public_id for row in load_predictions_allow_partial(out / "predictions.jsonl")
    ] == sorted(record.public_id for record in records)
    manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["prediction_count"] == 3
