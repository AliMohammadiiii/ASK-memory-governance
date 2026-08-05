"""Explicit continuity graph construction for authoritative split isolation."""
from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mgp_natural.util.io import iter_jsonl, write_json, write_jsonl
from mgp_natural.util.text import canonicalize_text, tokens


@dataclass
class UnionFind:
    parent: dict[str, str] = field(default_factory=dict)
    rank: dict[str, int] = field(default_factory=dict)

    def add(self, item: str) -> None:
        if item not in self.parent:
            self.parent[item] = item
            self.rank[item] = 0

    def find(self, item: str) -> str:
        self.add(item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


_TEMPLATE_TOKEN = re.compile(
    r"(?i)\b(?:assignment|homework|project|lab)\s*#?\s*\d+[A-Za-z]?\b"
)


def _text(item: dict[str, Any]) -> str:
    return " ".join(turn["text"] for turn in item.get("dialogue", []))


def _text_signature(item: dict[str, Any]) -> str:
    return hashlib.sha256(canonicalize_text(_text(item)).encode("utf-8")).hexdigest()


def _template_keys(item: dict[str, Any]) -> set[str]:
    return {
        f"assignment_template:{canonicalize_text(match.group(0))}"
        for match in _TEMPLATE_TOKEN.finditer(_text(item))
    }


def _feature_type(key: str) -> str:
    return key.split(":", 1)[0] if ":" in key else "untyped"


def _pair_count(size: int) -> int:
    return size * (size - 1) // 2


def build_components(
    items: list[dict[str, Any]],
    near_duplicate_threshold: float = 0.92,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Build connected components from all declared and text-derived continuity relations."""

    if len({item["item_id"] for item in items}) != len(items):
        raise ValueError("item IDs must be unique before continuity construction")
    union_find = UnionFind()
    key_to_items: dict[str, list[str]] = defaultdict(list)
    by_id = {item["item_id"]: item for item in items}
    for item in items:
        item_id = item["item_id"]
        union_find.add(item_id)
        declared = {str(key) for key in item.get("continuity_keys_private", [])}
        for key in declared | _template_keys(item):
            key_to_items[key].append(item_id)
        key_to_items[f"exact_text:{_text_signature(item)}"].append(item_id)

    linked_pairs_by_feature: Counter[str] = Counter()
    linked_groups_by_feature: Counter[str] = Counter()
    for key, members in key_to_items.items():
        if len(members) > 1:
            feature = _feature_type(key)
            linked_groups_by_feature[feature] += 1
            linked_pairs_by_feature[feature] += _pair_count(len(members))
        for member in members[1:]:
            union_find.union(members[0], member)

    texts = {item_id: _text(item) for item_id, item in by_id.items()}
    token_sets = {item_id: set(tokens(text)) for item_id, text in texts.items()}
    ids = sorted(by_id)
    near_edges = 0
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            if by_id[left].get("source_track") != by_id[right].get("source_track"):
                continue
            longest = max(len(texts[left]), len(texts[right]))
            if abs(len(texts[left]) - len(texts[right])) > max(100, 0.25 * longest):
                continue
            left_tokens = token_sets[left]
            right_tokens = token_sets[right]
            if not left_tokens and not right_tokens:
                similarity = 1.0
            elif not left_tokens or not right_tokens:
                similarity = 0.0
            else:
                similarity = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
            if similarity >= near_duplicate_threshold:
                union_find.union(left, right)
                near_edges += 1

    roots = {item_id: union_find.find(item_id) for item_id in ids}
    root_members: dict[str, list[str]] = defaultdict(list)
    for item_id, root in roots.items():
        root_members[root].append(item_id)
    component_ids = {
        root: "CC-" + hashlib.sha256("\n".join(sorted(members)).encode("utf-8")).hexdigest()[:16]
        for root, members in root_members.items()
    }
    assignment = {item_id: component_ids[root] for item_id, root in roots.items()}
    sizes = Counter(assignment.values())
    size_histogram = Counter(sizes.values())
    track_items = Counter(str(item.get("source_track", "UNKNOWN")) for item in items)
    track_components: dict[str, set[str]] = defaultdict(set)
    for item in items:
        track_components[str(item.get("source_track", "UNKNOWN"))].add(
            assignment[item["item_id"]]
        )

    report = {
        "schema_version": "1.0",
        "items": len(items),
        "components": len(sizes),
        "component_sizes": dict(sorted(sizes.items())),
        "component_size_histogram": {
            str(size): count for size, count in sorted(size_histogram.items())
        },
        "largest_component_size": max(sizes.values(), default=0),
        "largest_component_share": max(sizes.values(), default=0) / max(1, len(items)),
        "continuity_key_count": len(key_to_items),
        "continuity_feature_key_counts": dict(
            Counter(_feature_type(key) for key in key_to_items)
        ),
        "linked_groups_by_feature": dict(linked_groups_by_feature),
        "linked_pairs_by_feature": dict(linked_pairs_by_feature),
        "near_duplicate_threshold": near_duplicate_threshold,
        "near_duplicate_edges": near_edges,
        "exact_text_groups_with_duplicates": linked_groups_by_feature["exact_text"],
        "exact_text_duplicate_pairs": linked_pairs_by_feature["exact_text"],
        "track_items": dict(track_items),
        "track_components": {
            track: len(components) for track, components in sorted(track_components.items())
        },
        "status": "GENERATED",
    }
    return assignment, report


def build_graph_file(
    input_path: Path,
    assignments_path: Path,
    report_path: Path,
    near_duplicate_threshold: float = 0.92,
) -> dict[str, Any]:
    items = list(iter_jsonl(input_path))
    assignments, report = build_components(items, near_duplicate_threshold)
    write_jsonl(
        assignments_path,
        (
            {"item_id": item_id, "component_id": component_id}
            for item_id, component_id in sorted(assignments.items())
        ),
        mode=0o600,
    )
    write_json(report_path, report)
    return report

