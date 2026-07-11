# MGP-6 v2 Diagnostic

MGP-6 v2 is an author-designed diagnostic slice for memory-governance decisions in a long-term assistant. It tests whether a controller should `KEEP`, `SUPERSEDE`, or `ABSTAIN`, whether its resulting memory artifact is valid, and whether its answer uses only the active durable value.

This directory is a thesis-support method artifact and an internal evaluation dataset. It is not a general question-answering benchmark, not a measure of retrieval efficiency, and not yet a public multi-annotator benchmark.

## Contents

- `data/mgp6_v2.jsonl`: 180 synthetic scenarios, 30 for each of T1-T6.
- `mgp6_schema_v2.py`: Pydantic v2 row schema and transition invariants.
- `validate_mgp6.py`: row-level and strict corpus-level validation.
- `metrics_mgp6.py`: action, artifact, answer, safety, query-mode, and bootstrap metrics.
- `mgp6_v2_spec.md`: normative design and release limitations.
- `annotation_manual_v2.md`: annotation decision policy.
- `review/examples_review_sheet.csv`: one human-review row per scenario.

## Requirements and validation

Use Python 3.10 or newer and Pydantic 2.x. No other runtime package is required.

```bash
python3 mgp6_v2/validate_mgp6.py --input mgp6_v2/data/mgp6_v2.jsonl --strict
```

A valid release prints exactly:

```text
VALIDATION PASSED: 180 examples, 0 errors.
```

## Controller evaluation

Use a two-stage protocol. At the write stage, provide only `base_dialogue_prefix`,
`initial_memory_state`, and `perturbation_event`. The controller emits
`predicted_action` and `predicted_memory_state`. At the answer stage, reveal
`evaluation_query` and let the system answer from its predicted state. Do not
show the evaluation query before the write is committed; premise-resistance
queries can otherwise leak the stale candidate into governance.

The default closed-book track withholds `type`, `subtype`, `difficulty`, all
top-level source and temporal annotations, `conflict_type`, `semantic_slot`,
all `gold_*` fields, answer judges, rationales, rule identifiers, split-blocking
identifiers, and quality flags. Those fields are for scoring and analysis. An
oracle-metadata ablation may expose source annotations, but it must be named and
reported separately.

Write one prediction object per line with these fields:

- `scenario_id`: matching gold identifier.
- `predicted_action`: `KEEP`, `SUPERSEDE`, or `ABSTAIN`.
- `predicted_memory_state`: list of predicted memory-record dictionaries.
- `predicted_answer`: answer to `evaluation_query`.
- `confidence`: optional number in `[0, 1]` for risk-coverage analysis.

Run:

```bash
python3 mgp6_v2/metrics_mgp6.py \
  --gold mgp6_v2/data/mgp6_v2.jsonl \
  --pred predictions.jsonl \
  --bootstrap 1000
```

Add `--compare second_predictions.jsonl` for the paired exact McNemar helper. The full 180 rows are the primary reporting unit and the 90-row test split is secondary.

## Fair four-baseline protocol

Treat the four baselines as controlled ablations, not as equally capable
systems:

- B1 no-memory is a sanity floor and receives no stored state.
- B2 flat retrieval uses one declared retrieval unit and a fixed candidate
  budget; retrieval recall is reported separately from governance accuracy.
- B3 recency ranks by timestamp only. A query-conditioned prefilter is a
  different method and must not be called pure recency.
- B4 naive overwrite replaces any detected contradiction and has no abstention
  safeguard; its inability to emit `ABSTAIN` is an intended structural
  weakness, not missing data.

All memory-using systems receive the same raw evidence, context budget,
retrieval unit, and answer-stage query timing. Report action, artifact, and
answer metrics together; an action-only prediction with an empty state or
answer is valid input to the scorer but should score poorly on those outputs.

## LongMemEval bridge

MGP-6 v2 isolates write governance; LongMemEval-M tests whether the same memory
pipeline retrieves and uses information across long histories. Evaluate the
same controller separately on all 78 LongMemEval knowledge-update questions and
all 30 false-premise `_abs` questions, with retrieval recall and governance
errors reported separately. This is an external-validity bridge, not evidence
that either dataset substitutes for the other.

## Core fields

Each row contains its dialogue prefix, prior memory state, perturbation evidence, source and temporal metadata, gold action, auditable gold memory state, query mode, expected answer, regex judge specification, annotation rules, split-blocking identifiers, and quality flags. Memory text uses `semantic_slot = value`, which supports deterministic lineage and answer checks. Quality flags also record which downloaded-corpus pattern motivated a synthetic row; they are provenance aids and never model inputs in the default track.

`judge_spec.include` expresses required current content. `judge_spec.not_include` and `forbidden_answer_patterns` express stale or unsupported content. A correct answer must satisfy both presence and absence.

## Limitations

All examples are synthetic and low risk. No real personal data is included. The set targets selected failure modes and does not establish ecological validity, population coverage, or human inter-annotator agreement. Single-author construction can encode systematic assumptions; the review sheet supports a later independent review. Deletion, active forgetting, access control, general history QA, and multi-principal policy are out of scope for v2.
