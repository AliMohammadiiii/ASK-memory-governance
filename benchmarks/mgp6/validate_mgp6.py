#!/usr/bin/env python3
"""Strict structural and corpus-level validation for MGP-6 v2."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pydantic import ValidationError

try:
    from .mgp6_schema_v2 import MGP6Example, memory_value
except ImportError:
    from mgp6_schema_v2 import MGP6Example, memory_value


EXPECTED_FIELDS = frozenset(MGP6Example.model_fields)
TYPE_COUNTS = {f"T{i}": 30 for i in range(1, 7)}
ACTION_COUNTS = {"SUPERSEDE": 90, "KEEP": 24, "ABSTAIN": 66}
SPLIT_COUNTS = {"train": 60, "dev": 30, "test": 90}
QUERY_COUNTS = {
    "direct_recall": 108,
    "premise_resistance": 45,
    "implicit_application": 27,
}
PER_TYPE_SPLITS = {
    type_name: {"train": 10, "dev": 5, "test": 15}
    for type_name in TYPE_COUNTS
}
T5_SPLIT_ACTIONS = {
    "train": {"KEEP": 8, "ABSTAIN": 2},
    "dev": {"KEEP": 4, "ABSTAIN": 1},
    "test": {"KEEP": 12, "ABSTAIN": 3},
}
R4_CUES = (
    r"\bnow\b",
    r"\binstead\s+of\b",
    r"\bi\s+switched\b",
    r"\bactually\b",
    r"\bplease\s+remember\b",
    r"\bfrom\s+now\s+on\b",
)
REJECTION_RE = re.compile(
    r"\b(?:no|not|incorrect|wrong|false|stale|rather|instead|remains)\b",
    re.I,
)
META_APPLICATION_RE = re.compile(
    r"\b(?:apply the user's|without spelling out|current [a-z ]+ preference)\b",
    re.I,
)
ID_RE = re.compile(r"^MGP6V2-(T[1-6])-(TRAIN|DEV|TEST)-(\d{3})$")
PII_PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "phone": re.compile(r"(?<!\d)(?:\+?\d[ .-]?){8,}\d(?!\d)"),
    "street_address": re.compile(
        r"\b\d{1,5}\s+[A-Za-z][A-Za-z -]{1,30}\s+(?:street|st|road|rd|avenue|ave|lane|ln)\b",
        re.I,
    ),
}


def add_error(errors: list[str], message: str, line: int | None = None) -> None:
    prefix = f"line {line}: " if line is not None else "corpus: "
    errors.append(prefix + message)


def load_rows(path: Path, errors: list[str]) -> list[tuple[int, MGP6Example]]:
    rows: list[tuple[int, MGP6Example]] = []
    try:
        handle = path.open(encoding="utf-8")
    except OSError as exc:
        add_error(errors, f"cannot open {path}: {exc}")
        return rows
    with handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                add_error(errors, "blank JSONL line", line_number)
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                add_error(errors, f"invalid JSON: {exc.msg} at column {exc.colno}", line_number)
                continue
            if not isinstance(payload, dict):
                add_error(errors, "JSONL row must be an object", line_number)
                continue
            fields = frozenset(payload)
            if fields != EXPECTED_FIELDS:
                missing = sorted(EXPECTED_FIELDS - fields)
                extra = sorted(fields - EXPECTED_FIELDS)
                add_error(errors, f"field mismatch; missing={missing}, extra={extra}", line_number)
                continue
            try:
                rows.append((line_number, MGP6Example.model_validate(payload)))
            except ValidationError as exc:
                detail = "; ".join(
                    f"{'.'.join(map(str, item['loc']))}: {item['msg']}" for item in exc.errors()
                )
                add_error(errors, f"schema validation failed: {detail}", line_number)
    return rows


def expect_equal(errors: list[str], name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        add_error(errors, f"{name} expected {expected}, got {actual}")


def regex_matches(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.I) for pattern in patterns)


def validate_row(line: int, row: MGP6Example, errors: list[str]) -> None:
    match = ID_RE.fullmatch(row.scenario_id)
    if not match:
        add_error(errors, f"invalid scenario_id {row.scenario_id!r}", line)
    elif match.group(1) != row.type or match.group(2).lower() != row.split:
        add_error(errors, "scenario_id type/split does not match row labels", line)

    if row.type in {"T1", "T2", "T3"} and row.gold_action != "SUPERSEDE":
        add_error(errors, f"{row.type} must be SUPERSEDE", line)
    if row.type == "T4" and row.gold_action != "ABSTAIN":
        add_error(errors, "T4 must be ABSTAIN", line)
    if row.type == "T6" and row.gold_action != "ABSTAIN":
        add_error(errors, "T6 must be ABSTAIN", line)

    initial_ids = [record.id for record in row.initial_memory_state]
    gold_ids = [record.id for record in row.gold_memory_state]
    if len(initial_ids) != len(set(initial_ids)) or len(gold_ids) != len(set(gold_ids)):
        add_error(errors, "memory ids must be unique within each state", line)
    if not any(record.status == "active" for record in row.initial_memory_state):
        add_error(errors, "initial_memory_state has no active memory", line)

    gold_by_id = {record.id: record for record in row.gold_memory_state}
    for record in row.gold_memory_state:
        if record.supersedes_id and record.supersedes_id not in gold_by_id:
            add_error(errors, f"dangling supersedes_id {record.supersedes_id!r}", line)

    active = [record for record in row.gold_memory_state if record.status == "active"]
    active_texts = [record.text.casefold() for record in active]
    if len(active_texts) != len(set(active_texts)):
        add_error(errors, "duplicate equivalent active memory text", line)
    stable_records = [r for r in row.gold_memory_state if r.type == "stable_pref"]
    if stable_records:
        stable_active = [r for r in stable_records if r.status == "active"]
        if len(stable_active) != 1:
            add_error(errors, "stable-pref slot must have exactly one active stable memory", line)

    if row.gold_action == "SUPERSEDE":
        old = [record for record in row.gold_memory_state if record.status == "superseded"]
        successor = [record for record in active if record.supersedes_id]
        if not old or not successor:
            add_error(errors, "SUPERSEDE requires old superseded and successor active records", line)
        for record in old:
            stale = memory_value(record.text)
            if not regex_matches(row.forbidden_answer_patterns, stale):
                add_error(errors, f"forbidden patterns do not cover stale value {stale!r}", line)
            if not regex_matches(row.judge_spec.not_include, stale):
                add_error(errors, f"judge not_include does not cover stale value {stale!r}", line)
    elif row.gold_action == "ABSTAIN":
        if row.gold_memory_state != row.initial_memory_state:
            add_error(errors, "ABSTAIN changed the memory state", line)
    else:
        before = {r.id: r for r in row.initial_memory_state if r.status == "active"}
        after = {r.id: r for r in active}
        if not set(before).issubset(after):
            add_error(errors, "KEEP failed to preserve prior active durable memory", line)
        if any(r.type != "transient_pref" for rid, r in after.items() if rid not in before):
            add_error(errors, "KEEP added a non-transient memory", line)

    if row.gold_action in {"KEEP", "ABSTAIN"} and not regex_matches(
        row.forbidden_answer_patterns, row.perturbation_event
    ):
        add_error(errors, "unsupported or transient candidate is not covered in the event", line)

    if row.forbidden_answer_patterns != row.judge_spec.not_include:
        add_error(errors, "judge_spec.not_include must equal forbidden_answer_patterns", line)
    for pattern in row.judge_spec.include:
        if not re.search(pattern, row.expected_answer):
            add_error(errors, f"expected_answer misses include regex {pattern!r}", line)
    for pattern in row.judge_spec.not_include:
        if re.search(pattern, row.expected_answer):
            add_error(errors, f"expected_answer matches not_include regex {pattern!r}", line)

    active_values = [memory_value(record.text) for record in active]
    if not any(value.casefold() in row.expected_answer.casefold() for value in active_values):
        add_error(errors, "expected_answer does not use an active value", line)
    stale_values = [
        memory_value(record.text)
        for record in row.gold_memory_state
        if record.status == "superseded"
    ]
    if any(value.casefold() in row.expected_answer.casefold() for value in stale_values):
        add_error(errors, "expected_answer uses a superseded value", line)

    if row.query_mode == "premise_resistance":
        if not regex_matches(row.forbidden_answer_patterns, row.evaluation_query):
            add_error(errors, "premise-resistance query does not embed the forbidden premise", line)
        if not REJECTION_RE.search(row.expected_answer):
            add_error(errors, "premise-resistance answer does not reject the false premise", line)
    if row.query_mode == "implicit_application":
        if regex_matches(row.forbidden_answer_patterns, row.expected_answer):
            add_error(errors, "implicit-application answer names a forbidden old/candidate value", line)
        if regex_matches(row.judge_spec.include, row.evaluation_query):
            add_error(errors, "implicit-application query reveals the active value", line)
        if regex_matches(row.forbidden_answer_patterns, row.evaluation_query):
            add_error(errors, "implicit-application query reveals the old/candidate value", line)
        if META_APPLICATION_RE.search(row.evaluation_query):
            add_error(errors, "implicit-application query uses meta/template wording", line)

    if row.subtype == "implicit_conflict":
        if row.type not in {"T1", "T2", "T3"}:
            add_error(errors, "implicit_conflict subtype is only valid in T1-T3", line)
        if row.gold_action != "SUPERSEDE" or row.conflict_type != "implicit_invalidation":
            add_error(errors, "implicit conflict must be implicit_invalidation/SUPERSEDE", line)
        if row.difficulty not in {"hard", "adversarial"}:
            add_error(errors, "implicit conflict must be hard or adversarial", line)
        for cue in R4_CUES:
            if re.search(cue, row.perturbation_event, re.I):
                add_error(errors, f"implicit conflict contains R4 cue {cue!r}", line)

    required_flags = {"synthetic", "paraphrased_source_pattern", "judge_spec_gatemem_shape"}
    if row.type in {"T1", "T2", "T3"}:
        required_flags.add("source_pattern_longmemeval_knowledge_update")
    if row.query_mode == "premise_resistance":
        required_flags.add("source_pattern_longmemeval_false_premise")
    if row.query_mode == "implicit_application":
        required_flags.add("source_pattern_stale_implicit_application")
    if row.subtype == "implicit_conflict":
        required_flags.update({"cue_free", "source_pattern_stale_implicit_conflict"})
    if row.type == "T5":
        required_flags.add("source_pattern_memora_temporal_scope")
    if row.type == "T6":
        required_flags.add("source_pattern_memevobench_misleading_pool")
    missing_flags = sorted(required_flags - set(row.quality_flags))
    if missing_flags:
        add_error(errors, f"missing release quality flags: {missing_flags}", line)

    serialized = json.dumps(row.model_dump(mode="json"), ensure_ascii=True)
    for label, pattern in PII_PATTERNS.items():
        if pattern.search(serialized):
            add_error(errors, f"possible {label} detected", line)


def validate_corpus(rows: list[tuple[int, MGP6Example]], errors: list[str]) -> None:
    models = [row for _, row in rows]
    expect_equal(errors, "row count", len(models), 180)
    expect_equal(errors, "type counts", dict(Counter(r.type for r in models)), TYPE_COUNTS)
    expect_equal(errors, "action counts", dict(Counter(r.gold_action for r in models)), ACTION_COUNTS)
    expect_equal(errors, "split counts", dict(Counter(r.split for r in models)), SPLIT_COUNTS)
    expect_equal(errors, "query-mode counts", dict(Counter(r.query_mode for r in models)), QUERY_COUNTS)

    ids = [row.scenario_id for row in models]
    if len(ids) != len(set(ids)):
        duplicates = sorted(key for key, count in Counter(ids).items() if count > 1)
        add_error(errors, f"duplicate scenario ids: {duplicates}")

    per_type_split = {
        type_name: dict(Counter(r.split for r in models if r.type == type_name))
        for type_name in TYPE_COUNTS
    }
    expect_equal(errors, "per-type split counts", per_type_split, PER_TYPE_SPLITS)

    for split, expected in T5_SPLIT_ACTIONS.items():
        actual = dict(Counter(r.gold_action for r in models if r.type == "T5" and r.split == split))
        expect_equal(errors, f"T5 {split} action counts", actual, expected)

    for type_name in TYPE_COUNTS:
        subset = [row for row in models if row.type == type_name]
        modes = Counter(row.query_mode for row in subset)
        if modes["premise_resistance"] < 3 or modes["implicit_application"] < 2:
            add_error(errors, f"{type_name} misses query-mode floors: {dict(modes)}")
        difficulties = Counter(row.difficulty for row in subset)
        if difficulties["hard"] < 3 or difficulties["adversarial"] < 2:
            add_error(errors, f"{type_name} misses difficulty floors: {dict(difficulties)}")

    for split, size in SPLIT_COUNTS.items():
        modes = Counter(row.query_mode for row in models if row.split == split)
        if modes["premise_resistance"] < math.ceil(size * 0.15):
            add_error(errors, f"{split} misses the 15% premise-resistance floor: {dict(modes)}")
        if modes["implicit_application"] < math.ceil(size * 0.10):
            add_error(errors, f"{split} misses the 10% implicit-application floor: {dict(modes)}")

    family_splits: dict[str, set[str]] = defaultdict(set)
    pair_splits: dict[str, set[str]] = defaultdict(set)
    pair_rows: dict[str, list[MGP6Example]] = defaultdict(list)
    for row in models:
        family_splits[row.template_family_id].add(row.split)
        if row.minimal_pair_group_id:
            pair_splits[row.minimal_pair_group_id].add(row.split)
            pair_rows[row.minimal_pair_group_id].append(row)
    leaked_families = sorted(key for key, splits in family_splits.items() if len(splits) > 1)
    leaked_pairs = sorted(key for key, splits in pair_splits.items() if len(splits) > 1)
    if leaked_families:
        add_error(errors, f"template-family split leakage: {leaked_families}")
    if leaked_pairs:
        add_error(errors, f"minimal-pair split leakage: {leaked_pairs}")
    expect_equal(errors, "minimal-pair group count", len(pair_rows), 24)
    for pair_id, members in sorted(pair_rows.items()):
        if len(members) != 2:
            add_error(errors, f"{pair_id} must contain exactly two rows, got {len(members)}")
            continue
        sources = [row for row in members if row.type in {"T1", "T2", "T3"}]
        partners = [row for row in members if row.type == "T4"]
        if len(sources) != 1 or len(partners) != 1:
            add_error(errors, f"{pair_id} must pair one T1-T3 row with one T4 row")
            continue
        source, partner = sources[0], partners[0]
        if source.gold_action != "SUPERSEDE" or partner.gold_action != "ABSTAIN":
            add_error(errors, f"{pair_id} has an invalid action contrast")
        if source.semantic_slot != partner.semantic_slot or source.split != partner.split:
            add_error(errors, f"{pair_id} must share semantic_slot and split")
        source_old = [r for r in source.gold_memory_state if r.status == "superseded"]
        source_new = [r for r in source.gold_memory_state if r.status == "active"]
        partner_active = [
            r for r in partner.gold_memory_state if r.status == "active" and r.type != "transient_pref"
        ]
        if not source_old or not source_new or not partner_active:
            add_error(errors, f"{pair_id} lacks values required for contrast validation")
            continue
        old_value = memory_value(source_old[0].text)
        new_value = memory_value(source_new[0].text)
        if old_value.casefold() != memory_value(partner_active[0].text).casefold():
            add_error(errors, f"{pair_id} does not preserve the same prior active value")
        if not regex_matches(partner.forbidden_answer_patterns, new_value):
            add_error(errors, f"{pair_id} T4 partner does not forbid the source successor")
        if source.perturbation_event not in partner.perturbation_event:
            add_error(errors, f"{pair_id} T4 partner does not preserve the source surface claim")

    for type_name in ("T1", "T2", "T3"):
        implicit = [
            row for row in models if row.type == type_name and row.subtype == "implicit_conflict"
        ]
        if len(implicit) != 10:
            add_error(errors, f"{type_name} needs exactly 10 implicit conflicts, got {len(implicit)}")
        paired = 0
        for source in implicit:
            if not source.minimal_pair_group_id:
                continue
            partners = pair_rows[source.minimal_pair_group_id]
            if any(
                partner.type == "T4"
                and partner.gold_action == "ABSTAIN"
                and partner.split == source.split
                for partner in partners
            ):
                paired += 1
        if paired != 6:
            add_error(errors, f"{type_name} needs exactly 6 paired implicit conflicts, got {paired}")

    seen_content: set[tuple[str, str, str]] = set()
    seen_events: set[str] = set()
    for line, row in rows:
        normalized_event = re.sub(r"\s+", " ", row.perturbation_event.casefold()).strip()
        if normalized_event in seen_events:
            add_error(errors, "exact duplicate perturbation_event", line)
        seen_events.add(normalized_event)
        signature = (
            row.semantic_slot,
            normalized_event,
            re.sub(r"\s+", " ", row.evaluation_query.casefold()).strip(),
        )
        if signature in seen_content:
            add_error(errors, "exact duplicate slot/event/query signature", line)
        seen_content.add(signature)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="MGP-6 JSONL path")
    parser.add_argument("--strict", action="store_true", help="enable corpus-level constraints")
    args = parser.parse_args(argv)

    errors: list[str] = []
    rows = load_rows(args.input, errors)
    for line, row in rows:
        validate_row(line, row, errors)
    if args.strict:
        validate_corpus(rows, errors)

    if errors:
        print(f"VALIDATION FAILED: {len(errors)} errors.")
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print(f"VALIDATION PASSED: {len(rows)} examples, 0 errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
