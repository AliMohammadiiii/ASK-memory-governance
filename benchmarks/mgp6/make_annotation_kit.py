#!/usr/bin/env python3
"""Build a BLIND annotation kit for MGP-6 v2 independent annotation.

Produces, under --out-dir:
    blind_scenarios.jsonl   closed-book inputs only (no gold fields), shuffled
    annotation_sheet.csv    human-friendly sheet with empty label columns
    INSTRUCTIONS.md         annotator instructions (points to the manual)

The annotator sees EXACTLY what the write stage of every system sees:
``base_dialogue_prefix``, ``initial_memory_state``, ``perturbation_event``.
All gold / leaky fields (gold_action, gold_memory_state, type, subtype,
conflict_type, source_reliability, temporal_scope, rationale_notes,
annotation_rule_ids, judge_spec, expected_answer, ...) are stripped, and the
presentation order is shuffled so template families are not adjacent.

Usage:
    # full held-out test split (recommended for the paper)
    python3 make_annotation_kit.py --split test --out-dir annotation_kit_test

    # stratified subset of the full corpus (n per type, still blind)
    python3 make_annotation_kit.py --split all --per-type 10 \
        --out-dir annotation_kit_sub60

After annotation, score with:
    python3 compute_agreement_v2.py --gold data/mgp6_v2.jsonl \
        --annotations annotation_kit_test/annotation_sheet_filled.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

BLIND_FIELDS = ("scenario_id", "base_dialogue_prefix", "initial_memory_state", "perturbation_event")

INSTRUCTIONS = """# MGP-6 v2 Blind Annotation Instructions

You are labelling memory *write* decisions for a personal-assistant memory
system. For each item you see:

1. **Earlier dialogue** — what the user said in previous sessions.
2. **Current memory** — the record(s) the system currently stores.
3. **New event** — one new piece of information arriving now.

Choose exactly ONE action per item (column `annotator_action`):

- **SUPERSEDE** — the new event reliably states a *durable* replacement value
  for the same slot, coming from the user. The stored value should be
  replaced (old record retained as history).
- **KEEP** — the stored durable value should remain authoritative. Use this
  when the new event is only a clear *temporary* override ("just for
  tonight", "my usual still stands") or does not durably change the slot.
- **ABSTAIN** — do not commit. Use when evidence is not directly from the
  user (unattributed note, forum post, third party), is garbled or
  low-confidence, is a tool/assistant guess the user never confirmed, or is
  a hedged/uncertain temporary candidate.

Rules of engagement:

- Follow the decision procedure in `annotation_manual_v2.md` (provided
  separately). Read it fully BEFORE starting.
- Label independently. Do not discuss items with the dataset author until
  all labels are submitted.
- Do not consult the dataset file or any system output.
- If you are torn between two actions, pick the one the manual's decision
  tree yields, and note your hesitation in `annotator_notes`.
- Optionally fill `annotator_value` (the new slot value you would store, for
  SUPERSEDE/KEEP-with-override) and `annotator_confidence` (0-1).

Fill the columns in `annotation_sheet.csv` and save as
`annotation_sheet_filled.csv` in the same folder.
"""


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def flatten_dialogue(msgs: list[dict[str, Any]]) -> str:
    return "\n".join(f"{m.get('role')}: {m.get('content')}" for m in msgs)


def flatten_memory(state: list[dict[str, Any]]) -> str:
    lines = []
    for r in state:
        if r.get("status") == "active":
            lines.append(f"[{r.get('type')}] {r.get('text')} (confidence {r.get('confidence')})")
    return "\n".join(lines) or "(empty)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=HERE / "data" / "mgp6_v2.jsonl")
    parser.add_argument("--split", default="test", help="test|train|dev|all (default: test)")
    parser.add_argument(
        "--per-type", type=int, default=0, help="stratified subsample: n per T1..T6 (0 = all)"
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=HERE / "annotation_kit_test")
    args = parser.parse_args(argv)

    rows = load_rows(args.gold)
    if args.split != "all":
        rows = [r for r in rows if r.get("split") == args.split]
    if not rows:
        raise SystemExit(f"no rows for split={args.split}")

    rng = random.Random(args.seed)
    if args.per_type > 0:
        by_type: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            by_type.setdefault(r["type"], []).append(r)
        sampled: list[dict[str, Any]] = []
        for t in sorted(by_type):
            pool = sorted(by_type[t], key=lambda r: r["scenario_id"])
            rng.shuffle(pool)
            sampled.extend(pool[: args.per_type])
        rows = sampled
    rng.shuffle(rows)  # break template-family adjacency

    args.out_dir.mkdir(parents=True, exist_ok=True)

    blind_path = args.out_dir / "blind_scenarios.jsonl"
    with blind_path.open("w", encoding="utf-8") as handle:
        for r in rows:
            handle.write(json.dumps({k: r[k] for k in BLIND_FIELDS}, ensure_ascii=False) + "\n")

    sheet_path = args.out_dir / "annotation_sheet.csv"
    with sheet_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "item_no",
                "scenario_id",
                "earlier_dialogue",
                "current_memory",
                "new_event",
                "annotator_action",
                "annotator_value",
                "annotator_confidence",
                "annotator_notes",
            ]
        )
        for i, r in enumerate(rows, 1):
            writer.writerow(
                [
                    i,
                    r["scenario_id"],
                    flatten_dialogue(r["base_dialogue_prefix"]),
                    flatten_memory(r["initial_memory_state"]),
                    r["perturbation_event"],
                    "",
                    "",
                    "",
                    "",
                ]
            )

    (args.out_dir / "INSTRUCTIONS.md").write_text(INSTRUCTIONS, encoding="utf-8")

    from collections import Counter

    splits = Counter(r.get("split") for r in rows)
    print(f"[kit] {len(rows)} blind items -> {args.out_dir}")
    print(f"[kit] splits: {dict(splits)}")
    print("[kit] files: blind_scenarios.jsonl, annotation_sheet.csv, INSTRUCTIONS.md")
    print(
        "[kit] give the annotator: annotation_sheet.csv + INSTRUCTIONS.md + "
        "annotation_manual_v2.md (nothing else)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
