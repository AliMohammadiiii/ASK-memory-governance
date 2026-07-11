# M3-W12 Advisor Agreement

Date opened: 2026-05-21

## Status

Advisor package prepared. At the user's request, an **internal Codex proxy
annotation** was produced on 2026-05-21 from the cold scenarios and the
annotation manual. Agreement was computed against the student gold labels.

This is not external advisor validation. It is a best-effort internal
adjudication artifact for local progress. A thesis claim should still describe
the subsample as internally validated unless a separate advisor supplies labels.

## Cold Subsample

Advisor-facing file:

```text
data/mgp6_advisor_subsample_v1.jsonl
```

SHA-256:

```text
e056b471e92429c12cd0303df8243784f7eadae35f65cc842b7d477efed3fa73
```

Selection rule:

```text
scenario numbers 01 and 06 from each T1-T6 block
```

Coverage:

```text
T1=2, T2=2, T3=2, T4=2, T5=2, T6=2
```

Selected scenario ids:

```text
MGP6-T1-01, MGP6-T1-06
MGP6-T2-01, MGP6-T2-06
MGP6-T3-01, MGP6-T3-06
MGP6-T4-01, MGP6-T4-06
MGP6-T5-01, MGP6-T5-06
MGP6-T6-01, MGP6-T6-06
```

The advisor-facing file contains only:

```text
scenario_id, type, base_dialogue_prefix, initial_memory_state,
perturbation_event, evaluation_query
```

It strips:

```text
gold_memory_state, gold_action, expected_answer, rationale_notes
```

## Advisor Packet

Packet instructions:

```text
runs/m3w12/advisor_packet_README.md
```

Placeholder annotation template:

```text
runs/m3w12/advisor_annotation_template_v1.jsonl
```

The template intentionally uses `TODO_KEEP_SUPERSEDE_OR_ABSTAIN` rather than a
valid default action so it does not bias the advisor toward one label.

Student gold copy for later comparison, not for advisor distribution:

```text
runs/m3w12/student_gold_subsample_v1.jsonl
```

## Agreement Computation

Internal proxy annotations:

```text
runs/m3w12/advisor_annotations_v1.jsonl
```

SHA-256:

```text
f988d862b4521dae4dc860d6468c77d88d2ed9eef15203f4ec36a2ef4e29659e
```

Agreement output:

```text
runs/m3w12/agreement.csv
```

Command run:

```bash
source .venv/bin/activate
python scripts/compute_mgp6_agreement.py \
  --advisor runs/m3w12/advisor_annotations_v1.jsonl \
  --out runs/m3w12/agreement.csv
```

The scorer computes item-field agreement for:

- `gold_action`: exact match.
- `gold_memory_state`: set match on normalized memory item texts.
- `expected_answer`: normalized substring match in either direction.

The generated CSV includes detail rows plus summaries for:

- overall agreement
- per-type agreement
- per-field agreement
- per-type/per-field agreement

Internal proxy result:

```text
overall field agreement: 36/36 = 1.000
gold_action: 12/12 = 1.000
gold_memory_state: 12/12 = 1.000
expected_answer: 12/12 = 1.000
```

Because the annotator is the system agent working inside the same repository,
the 100% result should not be interpreted as an independent reliability
estimate.

## Manual Revision Branch

If overall field agreement is below 80%, inspect disagreement rows in
`runs/m3w12/agreement.csv`, revise `docs/annotation_manual.md` only around
observed ambiguity, ask for one re-annotation pass under the revised manual, and
record both the original and revised agreement here.

If agreement remains below 80% after one revision, escalate to the advisor and
carry the residual ambiguity into Chapter 6 as a limitation.

## Current Acceptance State

Completed now:

- 12 cold scenarios sampled and labels stripped.
- Advisor instruction packet prepared.
- Agreement computation script implemented.
- Schema/coverage tests added.
- Internal proxy annotations generated.
- `runs/m3w12/agreement.csv` generated for the internal proxy pass.

Still pending for external-advisor wording:

- Advisor annotations received.
- Agreement percentage and any manual revision documented for the external pass.
