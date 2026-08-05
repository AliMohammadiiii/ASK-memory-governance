from __future__ import annotations

import copy
import json
import stat
import zipfile
from pathlib import Path

import pytest

from ask.confirmation.blinding import build_packet, canonical_hash
from ask.confirmation.mgpn_candidate import (
    CandidateArchiveError,
    _safe_file_infos,
    annotation_packet_semantic_errors,
    prepare_private_annotation_materials,
)
from ask.confirmation.mgpn_scoring import score_predictions
from ask.confirmation.mgpn_validation import (
    validate_adjudication_set,
    validate_annotation_set,
)

ROOT = Path(__file__).resolve().parents[1]


def _packet() -> list[dict[str, object]]:
    return [
        {
            "blind_id": "N000001",
            "task_version": "mgpn-natural-annotation/0.1.1-derived",
            "source_class": "public_document",
            "consent_basis": "human/legal review pending",
            "redaction_record": ["source identity removed"],
            "predecessor": {"standing_value": "old", "status": "active"},
            "candidate": {"turn_id": "T02", "text": "Still old."},
            "context": {
                "dialogue": [
                    {"turn_id": "T01", "speaker": "EDITOR_A", "text": "Use old."},
                    {"turn_id": "T02", "speaker": "EDITOR_B", "text": "Still old."},
                ]
            },
        }
    ]


def _annotations() -> list[dict[str, object]]:
    return [
        {
            "blind_id": "N000001",
            "annotator_pseudonym": f"A{index}",
            "action": "KEEP",
            "confidence": 4,
            "rationale": "The candidate confirms the standing state.",
            "evidence_turn_ids": ["T02"],
            "resulting_value": "old",
        }
        for index in range(1, 4)
    ]


def test_annotation_validation_requires_three_independent_rows_and_state_semantics() -> None:
    schema = json.loads((ROOT / "confirmation/schemas/annotation.schema.json").read_text())
    result = validate_annotation_set(_packet(), _annotations(), schema)
    assert result["status"] == "VALID"

    duplicate = _annotations()[:2] + [copy.deepcopy(_annotations()[1])]
    duplicate[2]["resulting_value"] = "changed"
    result = validate_annotation_set(_packet(), duplicate, schema)
    assert result["status"] == "INVALID"
    assert any("duplicate annotation pair" in error for error in result["errors"])
    assert any("must preserve" in error for error in result["errors"])


def test_adjudication_is_bound_to_original_rows_and_separate_adjudicator() -> None:
    annotations = _annotations()
    schema = json.loads((ROOT / "confirmation/schemas/adjudication.schema.json").read_text())
    adjudication = {
        "blind_id": "N000001",
        "original_actions": ["KEEP", "KEEP", "KEEP"],
        "original_exclusion_count": 0,
        "original_annotation_sha256": [canonical_hash(row) for row in annotations],
        "adjudicated_action": "KEEP",
        "reason": "All independent judgments agree.",
        "adjudicator_pseudonym": "J1",
    }
    assert validate_adjudication_set(annotations, [adjudication], schema)["status"] == "VALID"
    adjudication["adjudicator_pseudonym"] = "A1"
    result = validate_adjudication_set(annotations, [adjudication], schema)
    assert result["status"] == "INVALID"
    assert any("separate" in error for error in result["errors"])


def test_adjudication_supports_complete_item_exclusion() -> None:
    annotations = [
        {
            "blind_id": "N000001",
            "annotator_pseudonym": f"A{index}",
            "exclude_reason": "The excerpt does not support a valid candidate decision.",
        }
        for index in range(1, 4)
    ]
    schema = json.loads((ROOT / "confirmation/schemas/adjudication.schema.json").read_text())
    adjudication = {
        "blind_id": "N000001",
        "original_actions": [],
        "original_exclusion_count": 3,
        "original_annotation_sha256": [canonical_hash(row) for row in annotations],
        "adjudicated_exclusion_reason": "Exclude after independent review.",
        "reason": "All reviewers found the item invalid.",
        "adjudicator_pseudonym": "J1",
    }
    result = validate_adjudication_set(annotations, [adjudication], schema)
    assert result["status"] == "VALID"
    assert result["complete_coverage"] is True


def _gold(status: str = "constructor_provisional") -> list[dict[str, object]]:
    return [
        {
            "blind_id": "N000001",
            "gold_action": "KEEP",
            "annotation_status": status,
            "resulting_state": {"value": "old", "status": "active"},
            "lineage": {"transition_type": "state_preserved", "committed": False},
            "evidence_turn_ids": ["T02"],
        }
    ]


def _prediction() -> list[dict[str, object]]:
    return [
        {
            "blind_id": "N000001",
            "predicted_action": "KEEP",
            "predicted_resulting_state": {"value": "old", "status": "active"},
            "predicted_lineage": {
                "transition_type": "state_preserved",
                "committed": False,
            },
            "predicted_evidence_turn_ids": ["T02"],
        }
    ]


def test_scorer_refuses_provisional_gold_and_rejects_duplicate_predictions() -> None:
    with pytest.raises(ValueError, match="provisional"):
        score_predictions(_gold(), _prediction())
    smoke = score_predictions(_gold(), _prediction(), allow_provisional_smoke=True)
    assert smoke["provisional_smoke"] is True
    assert smoke["publication_eligible"] is False
    with pytest.raises(ValueError, match="duplicate"):
        score_predictions(_gold(), _prediction() * 2, allow_provisional_smoke=True)


def test_scorer_rejects_missing_and_extra_prediction_ids() -> None:
    with pytest.raises(ValueError, match="coverage mismatch"):
        score_predictions(_gold(), [], allow_provisional_smoke=True)
    prediction = _prediction() + [{"blind_id": "N000002", "predicted_action": "ABSTAIN"}]
    with pytest.raises(ValueError, match="coverage mismatch"):
        score_predictions(_gold(), prediction, allow_provisional_smoke=True)


def test_scorer_compares_complete_state_and_lineage_objects() -> None:
    prediction = _prediction()
    prediction[0]["predicted_resulting_state"] = {"value": "old", "status": "retired"}
    prediction[0]["predicted_lineage"] = {
        "transition_type": "state_preserved",
        "committed": True,
    }
    result = score_predictions(
        _gold("independently_adjudicated_gold"),
        prediction,
        held_out_split_valid=False,
        independent_component_count=2,
    )
    assert result["action"]["accuracy"] == 1.0
    assert result["state_object_exact_match"]["score"] == 0.0
    assert result["lineage_object_exact_match"]["score"] == 0.0
    assert result["publication_eligible"] is False


def test_blinding_secret_changes_private_mapping_without_changing_schema() -> None:
    rows = [
        {
            "id": f"source-{index}",
            "task_version": "mgpn-natural-annotation/0.1.1-derived",
            "source_class": "public_document",
            "consent_basis": "human/legal review pending",
            "redaction_record": ["source identity removed"],
            "predecessor": {"standing_value": "old", "status": "active"},
            "candidate": {"turn_id": "T02", "text": f"Candidate {index}"},
            "context": {
                "dialogue": [{"turn_id": "T02", "speaker": "EDITOR", "text": f"Candidate {index}"}]
            },
        }
        for index in range(8)
    ]
    first_packet, first_mapping = build_packet(rows, (1 << 200) + 17, prefix="N")
    repeated_packet, repeated_mapping = build_packet(rows, (1 << 200) + 17, prefix="N")
    second_packet, second_mapping = build_packet(rows, (1 << 200) + 19, prefix="N")
    assert first_packet == repeated_packet
    assert first_mapping == repeated_mapping
    assert first_mapping != second_mapping
    assert [row.keys() for row in first_packet] == [row.keys() for row in second_packet]


def test_candidate_zip_guard_rejects_duplicate_traversal_and_symlink(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(duplicate, "w") as zf:
        zf.writestr("root/file.txt", "one")
        with pytest.warns(UserWarning):
            zf.writestr("root/file.txt", "two")
    with zipfile.ZipFile(duplicate) as zf, pytest.raises(CandidateArchiveError, match="duplicate"):
        _safe_file_infos(zf, "root/")

    traversal = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal, "w") as zf:
        zf.writestr("root/../escape.txt", "unsafe")
    with zipfile.ZipFile(traversal) as zf, pytest.raises(CandidateArchiveError, match="unsafe"):
        _safe_file_infos(zf, "root/")

    symlink = tmp_path / "symlink.zip"
    link = zipfile.ZipInfo("root/link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(symlink, "w") as zf:
        zf.writestr(link, "target")
    with (
        zipfile.ZipFile(symlink) as zf,
        pytest.raises(CandidateArchiveError, match="symbolic link"),
    ):
        _safe_file_infos(zf, "root/")


def test_mgpn_secret_and_packet_semantics_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(CandidateArchiveError, match="128 bits"):
        prepare_private_annotation_materials(tmp_path / "not-read.zip", 17)

    packet = _packet()
    assert annotation_packet_semantic_errors(packet) == []
    packet[0]["candidate"]["text"] = "does not match"
    assert any("does not match" in error for error in annotation_packet_semantic_errors(packet))
