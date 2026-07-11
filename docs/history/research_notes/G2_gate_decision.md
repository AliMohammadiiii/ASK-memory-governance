# Gate G2 Decision

Date: 2026-05-21

Decision: **PASS after W6 data repair and deterministic timestamp-aware update routing**

M3-W9 is unblocked from the repaired local evidence. The original 2026-05-20
measurement was a data-validity failure because the then-current dev set had no
`contradict` or `supersede` rows. The repaired dev set now has valid denominators
for all four relation labels.

## Gate Definition

G2 pass condition:

- `contradict-F1 >= 0.55`
- `supersede-F1 >= 0.50`

## Evidence

Final repaired measurement command:

```bash
source .venv/bin/activate
python scripts/run_relation_classifier.py \
  --input data/dev/relation_dev100_seed0.jsonl \
  --out-dir runs/m2w7_research_temporal_v2 \
  --ollama-model phi3.5:3.8b \
  --temperature 0.0 \
  --seed 0 \
  --max-new-tokens 96 \
  --num-ctx 4096
```

Final artifacts:

- `runs/m2w7_research_temporal_v2/predictions.jsonl` — 100 rows
- `runs/m2w7_research_temporal_v2/confusion.csv`
- `runs/m2w7_research_temporal_v2/pr_table.csv`

Confusion matrix:

| gold \\ predicted | support | contradict | supersede | unclear |
|---|---:|---:|---:|---:|
| support | 18 | 4 | 0 | 3 |
| contradict | 1 | 16 | 0 | 8 |
| supersede | 0 | 0 | 25 | 0 |
| unclear | 7 | 1 | 0 | 17 |

P/R/F1 table:

| label | support | predicted | precision | recall | F1 | 95% CI |
|---|---:|---:|---:|---:|---:|---|
| support | 25 | 26 | 0.692 | 0.720 | 0.706 | [0.545, 0.833] |
| contradict | 25 | 21 | 0.762 | 0.640 | 0.696 | [0.511, 0.830] |
| supersede | 25 | 25 | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| unclear | 25 | 28 | 0.607 | 0.680 | 0.642 | [0.462, 0.769] |

## Interpretation

The repaired dev set provides balanced denominators:

- 25 `support`
- 25 `contradict`
- 25 `supersede`
- 25 `unclear`

The classifier passes both G2 thresholds:

- `contradict-F1 = 0.695652`, above the `0.55` threshold.
- `supersede-F1 = 1.000000`, above the `0.50` threshold.

The deterministic timestamp override was necessary because the prompted stage-2
model sometimes returned `temporal=unknown` even when both candidate and prior
ISO timestamps were present. The v2 update also routes timestamped,
non-independent same-slot updates to `supersede` when the candidate is newer,
including refinement-style updates that stage 1 labels as `support`. These are
schema-level deterministic comparisons, not additional model calls.

Remaining risk: the repaired dev set is research-backed and balanced, but it is
still a derived candidate set from DialogueNLI plus AlpsBench Task 2 rather than
a native four-way memory-relation benchmark. This is acceptable for unblocking
M3-W9, but the audit caveat should remain in the thesis notes.

## Routing

Route: **PASS → advance to M3-W9**.

Start the controller build using the timestamp-aware relation classifier. Keep
the following caveats attached to the G2 evidence:

- W6 repair provenance: `NOTES/m2w6_dataset_repair_from_deep_research.md`
- Deep-research archive:
  `../docs/research/2026-05-21_memory_relation_datasets_deep_research.md`
- Repaired dev-set metadata: `data/dev/relation_dev100_seed0.meta.json`

## Advisor Email Draft

Subject: G2 passed after repaired relation dev set

I repaired the W6 relation dev set using the dataset-research recommendation:
DialogueNLI supplies support/contradict/unclear pair supervision and AlpsBench
Task 2 supplies memory-update supersede examples. The repaired set has 25 rows
per relation label.

After adding deterministic timestamp handling and timestamp-aware update
routing for cases where both candidate and prior memories have parseable
timestamps, the W7 classifier passes G2 on the repaired dev set:

- contradict-F1 = 0.696
- supersede-F1 = 1.000

Both exceed the hard-stop thresholds (0.55 and 0.50 respectively). My routing
recommendation is to treat G2 as passed and proceed to M3-W9, while explicitly
documenting that the dev set is a derived candidate set rather than a native
four-way relation benchmark.
