# M2-W7 Relation Classifier Error Audit

## Repaired Dev-Set Run

After the W6 data repair, deterministic timestamp handling, and timestamp-aware
update routing, the classifier was rerun on the balanced 100-row relation dev
set:

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

Final metrics:

| label | support | predicted | precision | recall | F1 | 95% CI |
|---|---:|---:|---:|---:|---:|---|
| support | 25 | 26 | 0.692 | 0.720 | 0.706 | [0.545, 0.833] |
| contradict | 25 | 21 | 0.762 | 0.640 | 0.696 | [0.511, 0.830] |
| supersede | 25 | 25 | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| unclear | 25 | 28 | 0.607 | 0.680 | 0.642 | [0.462, 0.769] |

The main residual errors are:

- `contradict -> unclear`: 8 rows.
- `unclear -> support`: 7 rows.
- `support -> contradict`: 4 rows.
- `support -> unclear`: 3 rows.

The prior `supersede -> support` and `supersede -> contradict` errors were
removed by deterministic timestamp-aware update routing. In this v2 run,
timestamped non-independent same-slot updates are routed to `supersede` when the
candidate is newer, even if stage 1 frames the update as a refinement/support
instead of a direct contradiction.

G2-relevant result: `contradict-F1=0.695652` and
`supersede-F1=1.000000`, so the repaired measurement clears the W8 thresholds.

## Run Summary

Base run:

```bash
source .venv/bin/activate
python scripts/run_relation_classifier.py \
  --input data/dev/relation_dev100_seed0.jsonl \
  --out-dir runs/m2w7 \
  --ollama-model phi3.5:3.8b \
  --temperature 0.0 \
  --seed 0 \
  --max-new-tokens 96 \
  --num-ctx 4096
```

Robustness run:

```bash
source .venv/bin/activate
python scripts/run_relation_classifier.py \
  --input data/dev/relation_dev100_seed0.jsonl \
  --out-dir runs/m2w7_t03 \
  --ollama-model phi3.5:3.8b \
  --temperature 0.3 \
  --seed 0 \
  --max-new-tokens 96 \
  --num-ctx 4096 \
  --resume
```

The `T=0.3` run initially failed after 76 rows because the model returned a
valid JSON object followed by extra text. `StructuredLLM` now extracts the first
balanced JSON object rather than a greedy brace span, and the relation runner
supports `--resume`.

## Metrics

From `runs/m2w7/pr_table.csv`:

| label | support | predicted | precision | recall | F1 | 95% CI |
|---|---:|---:|---:|---:|---:|---|
| support | 100 | 100 | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| contradict | 0 | 0 | N/A | N/A | N/A | N/A |
| supersede | 0 | 0 | N/A | N/A | N/A | N/A |
| unclear | 0 | 0 | N/A | N/A | N/A | N/A |

The synthetic W6 dev-100 contains only support examples. These numbers verify
pipeline behavior, schema stability, and the easy support path; they do not
measure contradiction or supersession quality for G2.

## Confusions

There are no observed confusions in the local run:

- annotation ambiguity: 0 examples
- extraction-upstream error: 0 examples
- classifier error: 0 examples

The requested "10 examples per error class" cannot be populated because the
local synthetic dev-100 produced no errors and no non-support labels. This is a
data limitation, not evidence that the classifier is robust on conversational
contradictions.

## Robustness

Comparison command:

```bash
source .venv/bin/activate
python scripts/compare_relation_robustness.py \
  --base runs/m2w7/predictions.jsonl \
  --jitter runs/m2w7_t03/predictions.jsonl
```

Output:

```json
{
  "contradict_f1_t0": null,
  "contradict_f1_t03": null,
  "delta": null,
  "identical_predictions": true,
  "n": 100
}
```

Contradict-F1 stability cannot be evaluated on this local artifact because
there are no contradict labels. The meaningful local robustness check is that
all 100 predictions remained identical under `T=0.3`.

## Follow-Up For W8

Before using this as G2 evidence, replace the synthetic dev-100 with a real
stratified set containing support, contradict, supersede, and unclear labels.
The W8 hard-stop thresholds require contradict-F1 and supersede-F1, and those
are undefined here.
