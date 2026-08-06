from __future__ import annotations

from pathlib import Path

import pytest

from mgp_natural.adjudication.validation import validate_adjudications
from mgp_natural.annotation.validation import row_hash
from mgp_natural.errors import ValidationError
from mgp_natural.util.io import write_jsonl


def _validate(tmp_path: Path, items: list[dict], annotations: list[dict], adjudications: list[dict]) -> None:
    item_path = tmp_path / "items.jsonl"
    annotation_path = tmp_path / "annotations.jsonl"
    adjudication_path = tmp_path / "adjudications.jsonl"
    write_jsonl(item_path, items)
    write_jsonl(annotation_path, annotations)
    write_jsonl(adjudication_path, adjudications)
    validate_adjudications(item_path, annotation_path, adjudication_path)


def test_valid_adjudications_fixture(tmp_path: Path) -> None:
    report = validate_adjudications(
        Path("data/fixtures/blind_items.jsonl"),
        Path("data/fixtures/annotations_valid.jsonl"),
        Path("data/fixtures/adjudications_valid.jsonl"),
        tmp_path / "report.json",
    )
    assert report["status"] == "VALID"


def test_mutated_original_annotation_detected(tmp_path: Path, blind_items, annotations, adjudications, clone) -> None:
    rows = clone(annotations)
    rows[0]["rationale"] = "mutated"
    with pytest.raises(ValidationError, match="wrong annotation hashes"):
        _validate(tmp_path, blind_items, rows, adjudications)


def test_wrong_annotation_hashes(tmp_path: Path, blind_items, annotations, adjudications, clone) -> None:
    rows = clone(adjudications)
    rows[0]["source_annotation_hashes"][0] = "0" * 64
    with pytest.raises(ValidationError, match="wrong annotation hashes"):
        _validate(tmp_path, blind_items, annotations, rows)


def test_wrong_action_multiset(tmp_path: Path, blind_items, annotations, adjudications, clone) -> None:
    rows = clone(adjudications)
    rows[0]["source_action_multiset"] = ["ABSTAIN", "ABSTAIN", "ABSTAIN"]
    with pytest.raises(ValidationError, match="action multiset"):
        _validate(tmp_path, blind_items, annotations, rows)


def test_adjudicator_must_be_separate(tmp_path: Path, blind_items, annotations, adjudications, clone) -> None:
    rows = clone(adjudications)
    rows[0]["adjudicator_pseudonym"] = "ann-a"
    with pytest.raises(ValidationError, match="separate"):
        _validate(tmp_path, blind_items, annotations, rows)


def test_incomplete_coverage(tmp_path: Path, blind_items, annotations, adjudications) -> None:
    with pytest.raises(ValidationError, match="incomplete adjudication coverage"):
        _validate(tmp_path, blind_items, annotations, adjudications[:-1])


def test_invalid_final_resolution(tmp_path: Path, blind_items, annotations, adjudications, clone) -> None:
    rows = clone(adjudications)
    rows[0]["final_action"] = "SUPERSEDE"
    rows[0]["final_resulting_value"] = blind_items[0]["prior_value"]
    with pytest.raises(ValidationError, match="changed state"):
        _validate(tmp_path, blind_items, annotations, rows)


def test_wrong_exclusion_count(tmp_path: Path, blind_items, annotations, adjudications, clone) -> None:
    rows = clone(adjudications)
    rows[0]["source_exclusion_count"] = 1
    with pytest.raises(ValidationError, match="exclusion count"):
        _validate(tmp_path, blind_items, annotations, rows)


def test_hash_function_is_canonical(annotations, clone) -> None:
    row = clone(annotations[0])
    reordered = dict(reversed(list(row.items())))
    assert row_hash(row) == row_hash(reordered)


def test_adjudication_protocol_version_is_pinned(tmp_path: Path, blind_items, annotations, adjudications, clone) -> None:
    rows = clone(adjudications)
    rows[0]["protocol_version"] = "changed-after-unsealing"
    with pytest.raises(ValidationError, match="protocol version"):
        _validate(tmp_path, blind_items, annotations, rows)

