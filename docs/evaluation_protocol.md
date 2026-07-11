# Evaluation Protocol

This repository treats benchmark artifacts as evidence only when both the run
directory and `ARTIFACT_MANIFEST.md` mark them as usable.

## MGP-6

- Frozen test set: `data/mgp6_v1_seed0.jsonl`.
- SHA-256: `12e17af530067f0ec1cefa1131898e2c8bd2414ef20cfc4c37fb936148e65701`.
- Valid post-fix evidence: `runs/m4w14_thesis_colab_20260608`.
- Invalid pre-fix evidence: `runs/m4w14` and `runs/m4w15`.

MGP-6 v1 is a frozen test slice. Do not tune controller thresholds, extraction
rules, or classifier behavior against this file and then present the same run as
an independent test result. Any tuning must use a separate dev slice and must be
versioned separately.

The valid MGP-6 result should be reported cautiously:

- controller action accuracy: 0.617
- naive-overwrite action accuracy: 0.517
- controller-minus-naive paired CI includes 0
- lineage recoverability: controller 1.0 vs naive-overwrite 0.0

## RC@C

Valid RC@C evidence is `runs/m4w15_thesis_colab_20260608`, replayed from the
valid controller action log in `runs/m4w14_thesis_colab_20260608`.

Report the configured default operating point as the headline result. The
threshold sweep is a risk-coverage characterization curve, not a source of a
retuned headline operating point.

## LongMemEval-S 50

Current accepted partial status:

- B1 no-memory: 18%
- B2 flat-vector: 38%
- B3 recency: 22%
- B4 naive-overwrite: missing
- controller: missing

LongMemEval-S is incomplete until B4 and controller are run under the same
policy and `scripts/summarize_m4w13.py --require-complete` succeeds. Until then,
the repository may cite B1/B2/B3 only as partial baseline evidence.

Final-candidate LongMemEval-S policy:

- slice: `data/slices/longmemeval_s_cleaned_50_seed0.jsonl`
- seed: 0
- bootstrap samples: 1000
- raw-turn fallback: false
- judge tier: Ollama `phi3.5:3.8b`

Same-model judged HF runs, raw-turn-fallback runs, API smoke runs, and incomplete
log-only directories are development evidence unless the manifest says
otherwise.

## Temporary-Update Claims

Temporary/context-bound memory remains a documented limitation in
`docs/known_limitations.md`. Do not claim scoped temporary-memory correctness
from the current valid MGP-6 run; T5/T6 are explicitly weak slices.

## Promotion Gates

Promotion scripts may reject otherwise complete runs. A rejection must not be
overridden in documentation. In particular, `runs/m4w14_thesis_colab_20260608`
is valid final-candidate evidence but not promoted final evidence because the
paired controller-vs-B4 action-accuracy CI includes 0.
