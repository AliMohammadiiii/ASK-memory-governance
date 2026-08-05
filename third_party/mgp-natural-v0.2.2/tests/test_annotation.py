from __future__ import annotations

from pathlib import Path

import pytest

from mgp_natural.annotation.validation import validate_annotation_row, validate_annotations
from mgp_natural.errors import ValidationError
from mgp_natural.util.io import write_jsonl


def test_valid_annotations_fixture(tmp_path: Path) -> None:
    report = validate_annotations(
        Path("data/fixtures/blind_items.jsonl"),
        Path("data/fixtures/annotations_valid.jsonl"),
        tmp_path / "report.json",
    )
    assert report["items"] == 3
    assert report["status"] == "VALID"


def _validate_rows(tmp_path: Path, items: list[dict], rows: list[dict]) -> None:
    item_path = tmp_path / "items.jsonl"
    row_path = tmp_path / "rows.jsonl"
    write_jsonl(item_path, items)
    write_jsonl(row_path, rows)
    validate_annotations(item_path, row_path, minimum_annotators=3)


def test_duplicate_annotator(tmp_path: Path, blind_items: list[dict], annotations: list[dict], clone) -> None:
    rows = clone(annotations)
    rows.append(clone(rows[0]))
    with pytest.raises(ValidationError, match="duplicate annotator"):
        _validate_rows(tmp_path, blind_items, rows)


def test_too_few_annotators(tmp_path: Path, blind_items: list[dict], annotations: list[dict]) -> None:
    rows = [row for row in annotations if row["annotator_pseudonym"] != "ann-c"]
    with pytest.raises(ValidationError, match="too few annotators"):
        _validate_rows(tmp_path, blind_items, rows)


@pytest.mark.parametrize(
    "mutation,message",
    [
        ({"evidence_turn_ids": ["T999"]}, "invalid evidence ID"),
        ({"evidence_turn_ids": ["T001"]}, "candidate turn"),
        ({"action": "INVALID"}, "invalid action"),
        ({"confidence": 6}, "confidence"),
        ({"rationale": ""}, "rationale"),
    ],
)
def test_invalid_annotation_fields(blind_items: list[dict], annotations: list[dict], clone, mutation: dict, message: str) -> None:
    row = clone(annotations[0])
    row.update(mutation)
    with pytest.raises(ValidationError, match=message):
        validate_annotation_row(row, blind_items[0])


def test_supersede_without_changed_state(blind_items: list[dict], annotations: list[dict], clone) -> None:
    row = clone(annotations[3])
    row["resulting_value"] = blind_items[1]["prior_value"]
    with pytest.raises(ValidationError, match="must change"):
        validate_annotation_row(row, blind_items[1])


@pytest.mark.parametrize("action", ["KEEP", "ABSTAIN"])
def test_keep_or_abstain_cannot_change_state(blind_items: list[dict], annotations: list[dict], clone, action: str) -> None:
    row = clone(annotations[0])
    row["action"] = action
    row["resulting_value"] = "changed"
    with pytest.raises(ValidationError, match="cannot change"):
        validate_annotation_row(row, blind_items[0])


def test_label_plus_exclusion(blind_items: list[dict], annotations: list[dict], clone) -> None:
    row = clone(annotations[0])
    row["exclude"] = True
    row["exclusion_reason"] = "Invalid item"
    with pytest.raises(ValidationError, match="labeled and excluded"):
        validate_annotation_row(row, blind_items[0])


def test_source_mapping_leakage(blind_items: list[dict], annotations: list[dict], clone) -> None:
    row = clone(annotations[0])
    row["notes"] = {"source_locator": "private"}
    with pytest.raises(ValidationError, match="leakage"):
        validate_annotation_row(row, blind_items[0])


def test_annotation_protocol_version_is_pinned(blind_items: list[dict], annotations: list[dict], clone) -> None:
    row = clone(annotations[0])
    row["protocol_version"] = "changed-after-unsealing"
    with pytest.raises(ValidationError, match="protocol version"):
        validate_annotation_row(row, blind_items[0])


def test_annotator_manual_version_is_pinned(blind_items: list[dict], annotations: list[dict], clone) -> None:
    row = clone(annotations[0])
    row["manual_version"] = "changed-after-unsealing"
    with pytest.raises(ValidationError, match="manual version"):
        validate_annotation_row(row, blind_items[0])


def test_agreement_report_includes_required_semantic_breakdowns(tmp_path: Path) -> None:
    from mgp_natural.annotation.agreement import analyze

    report = analyze(
        Path("data/fixtures/annotations_valid.jsonl"),
        tmp_path / "agreement.json",
        items_path=Path("data/fixtures/blind_items.jsonl"),
    )
    assert report["raw_exact_agreement"] == 1.0
    assert report["krippendorff_alpha_nominal"] == 1.0
    assert set(report["per_class_agreement"]) == {"KEEP", "SUPERSEDE", "ABSTAIN"}
    assert report["resulting_value_agreement"]["canonical_exact_match_rate"] == 1.0
    assert report["evidence_span_agreement"]["mean_pairwise_f1"] == 1.0
    assert "track=STUDYCHAT" in report["agreement_by_track_and_scope"]


def test_agreement_report_records_action_conflicts(tmp_path: Path, annotations: list[dict], clone) -> None:
    from mgp_natural.annotation.agreement import analyze

    rows = clone(annotations)
    rows[1]["action"] = "ABSTAIN"
    rows[1]["resulting_value"] = "concise"
    path = tmp_path / "annotations.jsonl"
    write_jsonl(path, rows)
    report = analyze(path)
    conflicts = report["disagreement_taxonomy"]["action_pair_conflicts"]
    assert conflicts["ABSTAIN|KEEP"] > 0
    assert report["raw_exact_agreement"] < 1.0

