from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ask.confirmation.blinding import canonical_hash, make_commitment
from ask.confirmation.mgpn_candidate import make_mgpn_annotation_rows

ROOT = Path(__file__).resolve().parents[1]


def _load_builder():
    path = ROOT / "scripts/confirmation/build_blind_packet.py"
    spec = importlib.util.spec_from_file_location("build_blind_packet", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_blind_packet_is_deterministic_and_removes_source_id() -> None:
    builder = _load_builder()
    rows = [
        {"id": "source-a", "predecessor": None, "candidate": {"text": "a"}, "context": {}},
        {"id": "source-b", "predecessor": {}, "candidate": {"text": "b"}, "context": {}},
    ]
    packet_a, mapping_a = builder.build_packet(rows, 7)
    packet_b, mapping_b = builder.build_packet(rows, 7)
    assert packet_a == packet_b
    assert mapping_a == mapping_b
    assert all("id" not in row and "blind_id" in row for row in packet_a)


def test_blind_packet_rejects_gold_anywhere() -> None:
    builder = _load_builder()
    with pytest.raises(ValueError, match="prohibited"):
        builder.build_packet(
            [
                {
                    "id": "source-a",
                    "predecessor": None,
                    "candidate": {"gold_action": "KEEP"},
                    "context": {},
                }
            ],
            1,
        )


def test_blind_packet_rejects_constructor_relation_cue() -> None:
    builder = _load_builder()
    with pytest.raises(ValueError, match="relation_to_prior"):
        builder.build_packet(
            [
                {
                    "id": "source-a",
                    "predecessor": None,
                    "candidate": {"text": "done", "relation_to_prior": "supersedes"},
                    "context": {},
                }
            ],
            1,
        )


def test_blind_packet_rejects_unknown_metadata_and_duplicate_source_ids() -> None:
    builder = _load_builder()
    row = {
        "id": "source-a",
        "predecessor": None,
        "candidate": {"text": "a"},
        "context": {},
    }
    with pytest.raises(ValueError, match="non-allowlisted"):
        builder.build_packet([{**row, "repository_url": "https://example.test"}], 1)
    with pytest.raises(ValueError, match="unique"):
        builder.build_packet([row, row], 1)


def test_private_reveal_map_path_is_confined(tmp_path: Path) -> None:
    builder = _load_builder()
    with pytest.raises(SystemExit, match="private-map"):
        builder._require_private_mapping_path(tmp_path / "mapping.json")
    builder._require_private_mapping_path(ROOT / ".private/test/mapping.json")


def test_natural_packet_prefix_and_public_commitment_do_not_disclose_seed() -> None:
    builder = _load_builder()
    rows = [
        {
            "id": "source-a",
            "task_version": "mgpn-natural-annotation/0.1.1-derived",
            "source_class": "public_document",
            "consent_basis": "public source; human review pending",
            "redaction_record": ["identity removed"],
            "predecessor": {
                "memory_slot": "wording",
                "principal": "editorial state",
                "scope": "article",
                "standing_value": "a",
                "status": "active",
            },
            "candidate": {"turn_id": "T01", "text": "b"},
            "context": {
                "dialogue": [{"turn_id": "T01", "speaker": "EDITOR", "text": "b"}],
                "evaluation_query": "Choose an action.",
                "construction_notice": "Constructor-normalized state.",
            },
        }
    ]
    packet, mapping = builder.build_packet(rows, 991, prefix="N")
    commitment, private_record = make_commitment(packet, mapping, 991)
    schema = json.loads((ROOT / "confirmation/schemas/natural_challenge.schema.json").read_text())
    assert not list(Draft202012Validator(schema).iter_errors(packet[0]))
    assert "blinding_secret" not in commitment
    assert commitment["blinding_secret_disclosed"] is False
    assert private_record["blinding_secret"] == "991"
    assert commitment["packet_sha256"] == canonical_hash(packet)


def test_mgpn_projection_removes_ids_relations_and_source_identity() -> None:
    record = {
        "mgpn_id": "MGPN01-00000000000000000000",
        "memory_before": {
            "memory_id": "MGPN01-00000000000000000000-M0",
            "memory_slot": "wording",
            "principal": "editorial state",
            "scope": "article",
            "standing_value": "old",
            "status": "active",
            "derivation": "constructor normalized",
        },
        "candidate": {
            "turn_id": "T02",
            "text": "Alice fixed it",
            "relation_to_prior": "supersedes",
        },
        "dialogue": [
            {
                "turn_id": "T01",
                "speaker": "Alice",
                "text": "Alice requested a fix",
                "timestamp_utc": "2026-01-01T00:00:00Z",
                "source_author": "Alice",
                "source_author_kind": "registered_username",
            },
            {
                "turn_id": "T02",
                "speaker": "Bob",
                "text": "Alice fixed it",
                "timestamp_utc": "2026-01-02T00:00:00Z",
                "source_author": "Bob",
                "source_author_kind": "registered_username",
            },
        ],
        "evaluation_query": "KEEP, SUPERSEDE, or ABSTAIN?",
        "gold_action": "SUPERSEDE",
        "gold_rationale": "done",
        "resulting_state": {"value": "new"},
        "lineage": {"transition_type": "supersession"},
        "annotation": {"status": "expert_provisional_seed"},
        "source": {"oldid": 1, "permalink": "https://example.test"},
    }
    rows, summary = make_mgpn_annotation_rows([record])
    builder = _load_builder()
    packet, _ = builder.build_packet(rows, 17, prefix="N")
    schema = json.loads((ROOT / "confirmation/schemas/natural_challenge.schema.json").read_text())
    assert list(Draft202012Validator(schema).iter_errors(packet[0])) == []
    serialized = json.dumps(packet)
    assert "MGPN01-" not in serialized
    assert "relation_to_prior" not in serialized
    assert "gold_action" not in serialized
    assert "source_author" not in serialized
    assert "Alice" not in serialized
    assert "Bob" not in serialized
    assert "PARTICIPANT_1" in serialized
    assert "[CONTRIBUTOR_" in serialized
    assert summary["redacted_text_occurrence_count"] >= 1


def test_annotation_schema_supports_label_or_exclusion_but_not_both() -> None:
    schema = json.loads((ROOT / "confirmation/schemas/annotation.schema.json").read_text())
    validator = Draft202012Validator(schema)
    labeled = {
        "blind_id": "N000001",
        "annotator_pseudonym": "A1",
        "action": "KEEP",
        "confidence": 4,
        "rationale": "No justified state change.",
        "evidence_turn_ids": ["T01"],
        "resulting_value": "old value",
    }
    excluded = {
        "blind_id": "N000001",
        "annotator_pseudonym": "A1",
        "exclude_reason": "Sensitive content requires escalation.",
    }
    assert not list(validator.iter_errors(labeled))
    assert not list(validator.iter_errors(excluded))
    assert list(validator.iter_errors({**labeled, "exclude_reason": "also excluded"}))


@pytest.mark.parametrize(
    "name",
    ["item", "annotation", "adjudication", "natural_challenge", "trajectory"],
)
def test_confirmation_schema_is_valid(name: str) -> None:
    schema = json.loads((ROOT / f"confirmation/schemas/{name}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
