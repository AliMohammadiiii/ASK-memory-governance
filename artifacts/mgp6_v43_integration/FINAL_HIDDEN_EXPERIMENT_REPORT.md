# MGP-6 v4.3 final hidden experiment report

## Scope and authorization

Release: MGP-6 v4.3.0-human-validated-final. The one pre-registered final
configuration was the ASK public-indexed-evidence live-model controller with
the conservative public-evidence ABSTAIN guard, OpenRouter, and requested model
qwen/qwen3.5-9b. Its frozen runtime controls are recorded in
experiments/mgp6_v43/FINAL_HIDDEN_CONFIG.json; the one-run authorization is
recorded in FINAL_HIDDEN_RUN_AUTHORIZATION.json. The control gate commit
af12517a15c9d9af4bb3bf95f7caee7330e6b243 passed GitHub Actions CI run
30189412351, and the control-artifact commit
1d21431ed1a6c56ff2a92af30e886e39063bb096 passed CI run 30189865044.

No hidden input or hidden gold was used for prompt design, model selection,
debugging, or hyperparameter selection. B1--B4, decision zero-shot, rules,
and ablation runs remain public-development evidence only and are not final
hidden comparators.

## Prediction seal before private scoring

The model run completed all 540 expected hidden predictions. Before private
scoring, the prediction file had 540 unique public identifiers and strict
540/540 coverage against the hidden-input IDs without gold. The manifest records
complete=true, hidden_gold_accessed=false, zero invalid responses, and this
prediction SHA-256:

e6a598799115c9fc80ae3e731f1b5d59a4947e48df5356b12ba518bafb846806

The raw-response and final run-manifest SHA-256 values are, respectively:

be2e9bf374538f5ccb1d58a621dd15712975b2c707cf4d681387b985b896e0e1
9737d307a1b42585632ab020d96545614e275f52b3517388419253d36760f9d7

One transport-level remote disconnect occurred after 432 durable predictions.
The runner's immutable-manifest and resume checks accepted only the same frozen
controls; the resumed invocation generated the remaining 108 predictions with
no duplicate identifier or changed prediction.

Only after these checks did the official local private scorer read hidden gold.
Its aggregate output is ignored under runs/; no hidden record, gold label,
component mapping, annotation, or raw model response is included in this report.

## Final private-scored result

| Metric | Value |
| --- | ---: |
| Items / coverage | 540 / 1.0000 |
| Accuracy | 0.8481 |
| Macro-F1 | 0.8479 |
| Accuracy, component-cluster 95% CI | [0.8037, 0.8889] |
| Macro-F1, component-cluster 95% CI | [0.8021, 0.8894] |
| Bootstrap | 5,000 component resamples, seed 4301 |
| Selective coverage / selective accuracy | 0.6926 / 0.8449 |
| Abstention precision / recall | 0.8554 / 0.7889 |

| Gold action | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| ABSTAIN | 0.8554 | 0.7889 | 0.8208 | 180 |
| KEEP | 0.7947 | 0.8389 | 0.8162 | 180 |
| SUPERSEDE | 0.8967 | 0.9167 | 0.9066 | 180 |

Gold rows and predicted columns in the confusion matrix:

| Gold \ Predicted | ABSTAIN | KEEP | SUPERSEDE |
| --- | ---: | ---: | ---: |
| ABSTAIN | 142 | 30 | 8 |
| KEEP | 18 | 151 | 11 |
| SUPERSEDE | 6 | 9 | 165 |

## Operational accounting

- Prediction actions: 166 ABSTAIN, 190 KEEP, 184 SUPERSEDE.
- Prompt tokens: 212,467; completion tokens: 4,000.
- Response latency: mean 1,673 ms; median 1,278 ms; p95 2,931 ms; minimum
  705 ms; maximum 12,626 ms; summed model-response latency 903.5 seconds.
- Failures: 1 transport-level disconnect, recovered by resume. In-client retry
  count: 0. Invalid response count: 0.
- Cost: unavailable. OpenRouter response telemetry provided no cost or price
  field, so no estimate is fabricated.

## Interpretation and limits

This is a single frozen configuration on a controlled synthetic diagnostic.
It is not a final hidden comparison against the public-development baselines or
ablations, and no paired system test is available. Component-cluster intervals
address within-component dependence, but do not establish real-world
generalization, deployment safety, or superiority over another final system.
LongMemEval remains a separate external-validation track.
