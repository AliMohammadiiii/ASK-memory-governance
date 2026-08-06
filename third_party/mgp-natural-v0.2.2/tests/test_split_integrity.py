from __future__ import annotations

from pathlib import Path

import pytest

from mgp_natural.errors import ValidationError
from mgp_natural.splitting.continuity import build_components
from mgp_natural.splitting.split import audit_split_features, build_splits
from mgp_natural.util.io import write_jsonl


def _item(item_id: str, track: str, keys: list[str], text: str, scope: str = "SESSION_TASK_STATE") -> dict:
    return {
        "item_id": item_id,
        "source_track": track,
        "scope": scope,
        "continuity_keys_private": keys,
        "dialogue": [{"turn_id": "T1", "role": "user", "text": text}],
    }


def test_studychat_user_and_chat_link_components() -> None:
    items = [
        _item("a", "STUDYCHAT", ["user:u1", "chat:c1"], "alpha"),
        _item("b", "STUDYCHAT", ["user:u1", "chat:c2"], "beta"),
        _item("c", "STUDYCHAT", ["user:u2", "chat:c3"], "gamma"),
    ]
    assignment, report = build_components(items)
    assert assignment["a"] == assignment["b"]
    assert assignment["a"] != assignment["c"]
    assert report["components"] == 2


def test_wikiconv_contributor_page_and_lineage_link_components() -> None:
    items = [
        _item("a", "WIKICONV", ["page:p", "contributor:e1"], "alpha", "WORDING_STATE"),
        _item("b", "WIKICONV", ["page:p", "contributor:e2"], "beta", "WORDING_STATE"),
        _item("c", "WIKICONV", ["page:q", "contributor:e2", "lineage:l"], "gamma", "WORDING_STATE"),
    ]
    assignment, _ = build_components(items)
    assert len(set(assignment.values())) == 1


def test_exact_duplicate_and_near_duplicate_linkage() -> None:
    items = [
        _item("a", "STUDYCHAT", ["user:u1"], "Use final dataset for the report now."),
        _item("b", "STUDYCHAT", ["user:u2"], "Use final dataset for the report now."),
        _item("c", "STUDYCHAT", ["user:u3"], "Use the final dataset for the report now."),
    ]
    assignment, report = build_components(items, near_duplicate_threshold=0.8)
    assert len(set(assignment.values())) == 1
    assert report["exact_text_groups_with_duplicates"] == 1
    assert report["near_duplicate_edges"] >= 1


def test_component_cannot_cross_splits(tmp_path: Path) -> None:
    items = [
        _item("a", "STUDYCHAT", ["user:u1"], "alpha"),
        _item("b", "STUDYCHAT", ["user:u1"], "beta"),
        _item("c", "STUDYCHAT", ["user:u2"], "gamma"),
    ]
    item_path = tmp_path / "items.jsonl"
    component_path = tmp_path / "components.jsonl"
    write_jsonl(item_path, items)
    write_jsonl(component_path, [
        {"item_id": "a", "component_id": "cc1"},
        {"item_id": "b", "component_id": "cc1"},
        {"item_id": "c", "component_id": "cc2"},
    ])
    build_splits(item_path, component_path, tmp_path / "manifest.jsonl", tmp_path / "report.json")
    assert audit_split_features(item_path, tmp_path / "manifest.jsonl")["status"] == "VALID"


def test_feature_crossing_detected(tmp_path: Path) -> None:
    items = [
        _item("a", "STUDYCHAT", ["user:u1"], "alpha"),
        _item("b", "STUDYCHAT", ["user:u1"], "beta"),
    ]
    item_path = tmp_path / "items.jsonl"
    manifest_path = tmp_path / "manifest.jsonl"
    write_jsonl(item_path, items)
    write_jsonl(manifest_path, [
        {"item_id": "a", "split": "train"},
        {"item_id": "b", "split": "hidden_test"},
    ])
    with pytest.raises(ValidationError, match="continuity feature crossing"):
        audit_split_features(item_path, manifest_path)


def test_component_coverage_must_be_complete(tmp_path: Path) -> None:
    item_path = tmp_path / "items.jsonl"
    component_path = tmp_path / "components.jsonl"
    write_jsonl(item_path, [_item("a", "STUDYCHAT", ["user:u"], "alpha")])
    write_jsonl(component_path, [])
    with pytest.raises(ValidationError, match="coverage"):
        build_splits(item_path, component_path, tmp_path / "m.jsonl", tmp_path / "r.json")


def test_single_component_split_is_blocked_not_mislabeled_valid(tmp_path: Path) -> None:
    item_path = tmp_path / "items.jsonl"
    component_path = tmp_path / "components.jsonl"
    write_jsonl(item_path, [_item("a", "STUDYCHAT", ["user:u1"], "alpha")])
    write_jsonl(component_path, [{"item_id": "a", "component_id": "cc1"}])
    report = build_splits(
        item_path,
        component_path,
        tmp_path / "manifest.jsonl",
        tmp_path / "report.json",
    )
    assert report["split_audit_passed"] is False
    assert report["status"] == "BLOCKED_INSUFFICIENT_COMPONENTS_FOR_THREE_WAY_SPLIT"
    assert report["empty_splits"]


def test_exact_duplicate_crossing_is_detected(tmp_path: Path) -> None:
    items = [
        _item("a", "STUDYCHAT", ["user:u1"], "same exact dialogue"),
        _item("b", "STUDYCHAT", ["user:u2"], "same exact dialogue"),
    ]
    item_path = tmp_path / "items.jsonl"
    manifest_path = tmp_path / "manifest.jsonl"
    write_jsonl(item_path, items)
    write_jsonl(
        manifest_path,
        [
            {"item_id": "a", "split": "train"},
            {"item_id": "b", "split": "hidden_test"},
        ],
    )
    with pytest.raises(ValidationError, match="continuity feature crossing"):
        audit_split_features(item_path, manifest_path)


def test_near_duplicate_crossing_is_detected(tmp_path: Path) -> None:
    items = [
        _item("a", "STUDYCHAT", ["user:u1"], "Use the final dataset for this report now"),
        _item("b", "STUDYCHAT", ["user:u2"], "Use final dataset for this report now"),
    ]
    item_path = tmp_path / "items.jsonl"
    manifest_path = tmp_path / "manifest.jsonl"
    write_jsonl(item_path, items)
    write_jsonl(
        manifest_path,
        [
            {"item_id": "a", "split": "train"},
            {"item_id": "b", "split": "development"},
        ],
    )
    with pytest.raises(ValidationError, match="continuity feature crossing"):
        audit_split_features(item_path, manifest_path, near_duplicate_threshold=0.7)

