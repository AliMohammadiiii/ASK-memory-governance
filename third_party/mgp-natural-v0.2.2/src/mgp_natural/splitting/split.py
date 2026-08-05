"""Stable component-level split assignment and leakage audits."""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from mgp_natural.errors import ValidationError
from mgp_natural.util.io import iter_jsonl, write_json, write_jsonl
from mgp_natural.util.text import canonicalize_text, tokens

SPLITS = ("train", "development", "hidden_test")


def assign_components(
    component_sizes: dict[str, int],
    seed: int = 1729,
    ratios: tuple[float, float, float] = (0.70, 0.15, 0.15),
) -> dict[str, str]:
    if abs(sum(ratios) - 1.0) > 1e-9:
        raise ValidationError("split ratios must sum to one")
    if any(size <= 0 for size in component_sizes.values()):
        raise ValidationError("component sizes must be positive")
    total = sum(component_sizes.values())
    targets = {split: ratio * total for split, ratio in zip(SPLITS, ratios, strict=True)}
    counts: Counter[str] = Counter()
    assignment: dict[str, str] = {}
    ordered = sorted(
        component_sizes,
        key=lambda component: (
            -component_sizes[component],
            hashlib.sha256(f"{seed}:{component}".encode()).hexdigest(),
        ),
    )
    for component in ordered:

        def objective(
            split: str, component_id: str = component
        ) -> tuple[float, int, str]:
            projected = counts[split] + component_sizes[component_id]
            normalized = projected / max(1.0, targets[split])
            return normalized, counts[split], split

        chosen = min(SPLITS, key=objective)
        assignment[component] = chosen
        counts[chosen] += component_sizes[component]
    return assignment


def _dialogue_text(item: dict[str, Any]) -> str:
    return " ".join(turn["text"] for turn in item.get("dialogue", []))


def audit_split_features(
    items_path: Path,
    manifest_path: Path,
    near_duplicate_threshold: float = 0.92,
) -> dict[str, Any]:
    items = {row["item_id"]: row for row in iter_jsonl(items_path)}
    manifest_rows = list(iter_jsonl(manifest_path))
    split = {row["item_id"]: row["split"] for row in manifest_rows}
    if set(items) != set(split):
        raise ValidationError("split manifest coverage must exactly match items")

    feature_splits: dict[str, set[str]] = defaultdict(set)
    feature_types: Counter[str] = Counter()
    for item_id, item in items.items():
        for key in item.get("continuity_keys_private", []):
            key_text = str(key)
            feature_splits[key_text].add(split[item_id])
            feature_types[key_text.split(":", 1)[0]] += 1
    feature_crossing = {
        key: values for key, values in feature_splits.items() if len(values) > 1
    }

    exact_splits: dict[str, set[str]] = defaultdict(set)
    texts: dict[str, str] = {}
    for item_id, item in items.items():
        text = _dialogue_text(item)
        texts[item_id] = text
        signature = hashlib.sha256(canonicalize_text(text).encode()).hexdigest()
        exact_splits[signature].add(split[item_id])
    exact_crossing = sum(len(values) > 1 for values in exact_splits.values())

    near_crossing = 0
    token_sets = {item_id: set(tokens(text)) for item_id, text in texts.items()}
    ids = sorted(items)
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            if split[left] == split[right]:
                continue
            if items[left].get("source_track") != items[right].get("source_track"):
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
                near_crossing += 1

    source_family_prefixes = {
        "user",
        "chat",
        "artifact",
        "assignment_template",
        "page",
        "page_family",
        "thread",
        "section",
        "contributor",
        "revision_lineage",
        "deletion_restoration",
    }
    source_family_crossing = sum(
        len(values) > 1
        for key, values in feature_splits.items()
        if key.split(":", 1)[0] in source_family_prefixes
    )
    crossing_count = len(feature_crossing) + exact_crossing + near_crossing
    if crossing_count:
        raise ValidationError(
            "continuity feature crossing detected: "
            f"declared={len(feature_crossing)}, exact={exact_crossing}, near={near_crossing}"
        )
    return {
        "schema_version": "1.0",
        "features": len(feature_splits),
        "feature_counts_by_type": dict(feature_types),
        "crossing_features": 0,
        "source_family_crossing": source_family_crossing,
        "exact_text_crossing_groups": exact_crossing,
        "near_duplicate_crossing_pairs": near_crossing,
        "near_duplicate_threshold": near_duplicate_threshold,
        "status": "VALID",
    }


def build_splits(
    items_path: Path,
    component_path: Path,
    manifest_path: Path,
    report_path: Path,
    seed: int = 1729,
) -> dict[str, Any]:
    items = {row["item_id"]: row for row in iter_jsonl(items_path)}
    components = {row["item_id"]: row["component_id"] for row in iter_jsonl(component_path)}
    if set(items) != set(components):
        raise ValidationError("component coverage must exactly match items")
    component_members: dict[str, list[str]] = defaultdict(list)
    for item_id, component in components.items():
        component_members[component].append(item_id)
    component_split = assign_components(
        {key: len(value) for key, value in component_members.items()}, seed=seed
    ) if component_members else {}

    rows = [
        {
            "item_id": item_id,
            "component_id": components[item_id],
            "split": component_split[components[item_id]],
            "source_track": items[item_id]["source_track"],
            "scope": items[item_id]["scope"],
        }
        for item_id in sorted(items)
    ]
    observed: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        observed[row["component_id"]].add(row["split"])
    crossing = {
        component: sorted(splits) for component, splits in observed.items() if len(splits) > 1
    }
    if crossing:
        raise ValidationError(f"continuity components cross splits: {len(crossing)}")
    write_jsonl(manifest_path, rows, mode=0o600)
    feature_audit = audit_split_features(items_path, manifest_path)

    split_counts = Counter(row["split"] for row in rows)
    component_counts = Counter(component_split.values())
    empty_splits = [split for split in SPLITS if split_counts[split] == 0]
    sufficient_components = len(component_members) >= len(SPLITS)
    split_audit_passed = not empty_splits and sufficient_components
    status = (
        "VALID_COMPONENT_DISJOINT"
        if split_audit_passed
        else "BLOCKED_INSUFFICIENT_COMPONENTS_FOR_THREE_WAY_SPLIT"
    )
    total = len(rows)
    report = {
        "schema_version": "1.0",
        "status": status,
        "split_audit_passed": split_audit_passed,
        "items": total,
        "components": len(component_members),
        "split_counts": {split: split_counts[split] for split in SPLITS},
        "split_shares": {
            split: split_counts[split] / max(1, total) for split in SPLITS
        },
        "component_counts": {split: component_counts[split] for split in SPLITS},
        "component_to_split": dict(sorted(component_split.items())),
        "empty_splits": empty_splits,
        "crossing_components": 0,
        "feature_audit": feature_audit,
        "seed": seed,
        "note": "Balance is subordinate to continuity isolation.",
    }
    write_json(report_path, report)
    return report

