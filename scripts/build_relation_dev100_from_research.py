#!/usr/bin/env python3
"""Build a balanced relation-dev set from the dataset research recommendation.

The deep-research conclusion was that no public dataset exposes the exact
prior-memory/candidate-memory/four-way-relation unit directly. This builder
therefore creates a reproducible candidate set from the strongest practical
stack:

- AlpsBench Task 2 dev/validation rows for `supersede`.
- DialogueNLI pair labels for `support`, `contradict`, and `unclear`.

The output is suitable for classifier runs, but it should still be manually
audited before being treated as final thesis evidence.
"""

from __future__ import annotations

import argparse
import json
import random
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

RELATION_LABELS = ("support", "contradict", "supersede", "unclear")
DNLI_LABEL_TO_RELATION = {0: "support", 1: "unclear", 2: "contradict"}

ALPS_BASE = "https://huggingface.co/datasets/Cosineyx/Alpsbench/resolve/main"
ALPS_TASK2_PATHS = (
    "dataset/dev/task2",
    "dataset/validation/task2",
)
DNLI_ROWS_URL = "https://datasets-server.huggingface.co/rows"


def _read_json_url(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _read_jsonl_url(url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with urllib.request.urlopen(url, timeout=120) as response:
        for raw in response:
            if raw.strip():
                rows.append(json.loads(raw.decode("utf-8")))
    return rows


def _compact_text(value: str | None, *, max_chars: int = 600) -> str:
    text = " ".join((value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _looks_english(text: str) -> bool:
    if not text:
        return False
    ascii_chars = sum(1 for char in text if ord(char) < 128)
    return ascii_chars / len(text) >= 0.85


def _dialogue_memory_type(row: dict[str, Any]) -> str:
    triple = row.get("triple1") or row.get("triple2") or []
    predicate = str(triple[1] if len(triple) > 1 else "").lower()
    text = f"{row.get('sentence1', '')} {row.get('sentence2', '')}".lower()
    preference_markers = (
        "like",
        "dislike",
        "favorite",
        "prefer",
        "love",
        "hate",
        "hobby",
        "activity",
        "music",
        "food",
        "animal",
        "sports",
    )
    if any(marker in predicate or marker in text for marker in preference_markers):
        return "stable_pref"
    return "episodic_fact"


def _alps_memory_type(memory: dict[str, Any]) -> str:
    label = str(memory.get("label") or memory.get("label_suggestion") or "").lower()
    attitude = memory.get("preference_attitude")
    time_scope = str(memory.get("time_scope") or "").lower()
    value = str(memory.get("value") or "").lower()
    if "preference" in label or attitude is not None:
        return "stable_pref"
    if time_scope == "current":
        return "transient_pref"
    if any(token in value for token in ("prefer", "likes", "dislikes", "favorite")):
        return "stable_pref"
    return "episodic_fact"


def _gold_label(memory_type: str, relation: str) -> dict[str, Any]:
    return {
        "type": memory_type,
        "relation_to_prior_state": relation,
        "polarity_subject_expected": "user",
        "negation_expected": False,
        "hedge_expected": False,
        "marker_correctness": "Needs manual audit",
    }


def _dnli_page(split: str, offset: int, length: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "dataset": "pietrolesci/dialogue_nli",
            "config": "default",
            "split": split,
            "offset": offset,
            "length": length,
        }
    )
    data = _read_json_url(f"{DNLI_ROWS_URL}?{query}")
    return [item["row"] for item in data.get("rows", [])]


def _build_dnli_rows(seed: int, per_label: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    offset = 0
    page_size = 100
    while (
        min((len(buckets[label]) for label in ("support", "contradict", "unclear")), default=0)
        < per_label
    ):
        rows = _dnli_page("train", offset, page_size)
        if not rows:
            break
        for row in rows:
            relation = DNLI_LABEL_TO_RELATION.get(row.get("label"))
            if relation not in {"support", "contradict", "unclear"}:
                continue
            sentence1 = _compact_text(row.get("sentence1"))
            sentence2 = _compact_text(row.get("sentence2"))
            if not sentence1 or not sentence2:
                continue
            memory_type = _dialogue_memory_type(row)
            row_id = str(row.get("id") or f"offset-{offset}")
            buckets[relation].append(
                {
                    "turn_id": f"dnli-{row_id}",
                    "session_id": f"dnli-{row_id}",
                    "turn_idx": 0,
                    "role": "user",
                    "content": sentence1,
                    "extractor_item_text": sentence1,
                    "expected_extraction": f"{memory_type}: {sentence1}",
                    "timestamp": None,
                    "surrounding_window": [None, None],
                    "prior_memory": {
                        "memory_id": f"prior-dnli-{row_id}",
                        "text": sentence2,
                        "type": memory_type,
                        "timestamp": None,
                    },
                    "gold_label": _gold_label(memory_type, relation),
                    "source_file": "hf://datasets/pietrolesci/dialogue_nli/default/train",
                    "strata": {
                        "relation_label": relation,
                        "relation_source": "deep_research_stack_dialogue_nli_pair_label",
                        "dnli_original_label": row.get("original_label"),
                        "dnli_dtype": row.get("dtype"),
                        "dnli_triple1": row.get("triple1"),
                        "dnli_triple2": row.get("triple2"),
                    },
                    "adjudication_note": (
                        "Mapped from DialogueNLI pair label; manual audit required for "
                        "memory-slot fit and personal-memory validity."
                    ),
                }
            )
        offset += page_size
        if offset >= 10000:
            break

    converted: list[dict[str, Any]] = []
    for relation in ("support", "contradict", "unclear"):
        rng.shuffle(buckets[relation])
        converted.extend(buckets[relation][:per_label])
    return converted


def _find_old_memory(input_row: dict[str, Any], memory_id: str) -> dict[str, Any] | None:
    for memory in input_row.get("input", {}).get("memory", []):
        if memory.get("memory_id") == memory_id:
            return memory
    return None


def _last_user_turn(input_row: dict[str, Any]) -> str:
    turns = input_row.get("input", {}).get("new_dialogue", [])
    for turn in reversed(turns):
        if turn.get("role") == "user" and turn.get("text"):
            return _compact_text(turn["text"])
    for turn in reversed(input_row.get("input", {}).get("old_dialogue", [])):
        if turn.get("role") == "user" and turn.get("text"):
            return _compact_text(turn["text"])
    return ""


def _build_alps_supersede_rows(seed: int, needed: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for task_path in ALPS_TASK2_PATHS:
        input_rows = _read_jsonl_url(f"{ALPS_BASE}/{task_path}/model_input.jsonl")
        gold_rows = _read_jsonl_url(f"{ALPS_BASE}/{task_path}/reference_output.jsonl")
        input_by_id = {row["benchmark_id"]: row for row in input_rows}
        for gold_row in gold_rows:
            input_row = input_by_id.get(gold_row.get("benchmark_id"))
            if not input_row:
                continue
            for updated in gold_row.get("gold", {}).get("answer", []):
                updated_id = str(updated.get("memory_id", ""))
                if not updated_id.endswith("_updated"):
                    continue
                old_id = updated_id.removesuffix("_updated")
                prior = _find_old_memory(input_row, old_id)
                if not prior:
                    continue
                prior_text = _compact_text(prior.get("value"))
                candidate_text = _compact_text(updated.get("value"))
                if not prior_text or not candidate_text or prior_text == candidate_text:
                    continue
                if not (_looks_english(prior_text) and _looks_english(candidate_text)):
                    continue
                memory_type = _alps_memory_type(updated)
                benchmark_id = str(gold_row.get("benchmark_id"))
                source_turn = _last_user_turn(input_row)
                candidates.append(
                    {
                        "turn_id": f"alps-task2-{benchmark_id}-{updated_id}",
                        "session_id": str(gold_row.get("session_id") or benchmark_id),
                        "turn_idx": 0,
                        "role": "user",
                        "content": source_turn or candidate_text,
                        "extractor_item_text": candidate_text,
                        "expected_extraction": f"{memory_type}: {candidate_text}",
                        "timestamp": updated.get("updated_at"),
                        "surrounding_window": [None, None],
                        "prior_memory": {
                            "memory_id": f"prior-alps-{benchmark_id}-{old_id}",
                            "text": prior_text,
                            "type": memory_type,
                            "timestamp": prior.get("updated_at"),
                        },
                        "gold_label": _gold_label(memory_type, "supersede"),
                        "source_file": f"hf://datasets/Cosineyx/Alpsbench/{task_path}",
                        "strata": {
                            "relation_label": "supersede",
                            "relation_source": "deep_research_stack_alpsbench_task2_updated_memory",
                            "alps_stratum": input_row.get("stratum"),
                            "alps_old_memory_id": old_id,
                            "alps_updated_memory_id": updated_id,
                            "alps_old_label": prior.get("label"),
                            "alps_updated_label": updated.get("label"),
                        },
                        "adjudication_note": (
                            "Mapped from AlpsBench Task 2 gold updated memory; manual "
                            "audit required for atomicity and same-slot replacement."
                        ),
                    }
                )

    rng = random.Random(seed)
    rng.shuffle(candidates)
    return candidates[:needed]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")


def _write_meta(path: Path, rows: list[dict[str, Any]], seed: int) -> None:
    counts = Counter(row["gold_label"]["relation_to_prior_state"] for row in rows)
    meta = {
        "seed": seed,
        "n": len(rows),
        "label_counts": dict(sorted(counts.items())),
        "source_report": "docs/research/2026-05-21_memory_relation_datasets_deep_research.md",
        "sources": [
            "hf://datasets/Cosineyx/Alpsbench/dataset/dev/task2",
            "hf://datasets/Cosineyx/Alpsbench/dataset/validation/task2",
            "hf://datasets/pietrolesci/dialogue_nli/default/train",
        ],
        "audit_status": "candidate_set_needs_manual_audit",
        "mapping_summary": {
            "support": "DialogueNLI entailment pairs",
            "contradict": "DialogueNLI contradiction pairs",
            "supersede": "AlpsBench Task 2 gold memories with *_updated memory_id",
            "unclear": "DialogueNLI neutral pairs",
        },
    }
    path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build(seed: int) -> list[dict[str, Any]]:
    rows = []
    rows.extend(_build_dnli_rows(seed, per_label=25))
    rows.extend(_build_alps_supersede_rows(seed, needed=25))
    counts = Counter(row["gold_label"]["relation_to_prior_state"] for row in rows)
    missing = {label: 25 - counts[label] for label in RELATION_LABELS if counts[label] < 25}
    if missing:
        raise RuntimeError(f"could not build balanced dev set; missing rows: {missing}")

    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_label[row["gold_label"]["relation_to_prior_state"]].append(row)
    balanced: list[dict[str, Any]] = []
    for label in RELATION_LABELS:
        balanced.extend(by_label[label][:25])
    random.Random(seed).shuffle(balanced)
    return balanced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/dev/relation_dev100_research_seed0.jsonl"),
    )
    parser.add_argument(
        "--meta-out",
        type=Path,
        default=Path("data/dev/relation_dev100_research_seed0.meta.json"),
    )
    args = parser.parse_args(argv)

    rows = build(args.seed)
    _write_jsonl(args.out, rows)
    _write_meta(args.meta_out, rows, args.seed)
    counts = Counter(row["gold_label"]["relation_to_prior_state"] for row in rows)
    print(
        json.dumps({"out": str(args.out), "n": len(rows), "label_counts": counts}, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
