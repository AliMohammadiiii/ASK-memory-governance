# MGP-6 v4.3 development experiment report

## Scope and boundary

This is a completed development-only evaluation of the `decision_zero_shot`
configuration. It used the public 180-record development split and its public
development labels. It did not read hidden inputs, hidden gold, final human
gold, private mappings, or audit records. It is not a final hidden result and
must not be reported as real-world generalization.

## Executed configuration

```text
python3 scripts/run_mgp6_v43.py \
  --input benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl \
  --out runs/mgp6_v43/dev/decision_zero_shot_qwen35_9b \
  --system decision_zero_shot \
  --provider openrouter \
  --base-url https://openrouter.ai/api/v1 \
  --api-key-env OPENROUTER_API_KEY \
  --model-id qwen/qwen3.5-9b \
  --seed 4301 \
  --max-new-tokens 128 \
  --reasoning-effort none \
  --parse-retry-max-attempts 2
```

- Release: `MGP-6 v4.3.0-human-validated-final`.
- Dataset: `benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl`
  (`d4dbf740d9fa5239829842e2ab6f5ce67b11d6d909628ff38f4a19fc0242cde5`).
- Runner commit: `ed190cef4a0a1567f73f8cd786b9693b5ee28944`.
- Prompt hash: `556ab1a9202f7de60a8264b557abd5883ca4abcaf3f143fa14e4349243b3ab16`.
- System-prompt hash: `f04ed7648898e5331f1095422b030f2a0ed95660a85576af6e0f460e6f2a56ef`.
- Decoding: temperature 0.0, maximum 128 new tokens, reasoning effort `none`.
- Retry policy: 3 transport attempts and 2 parse attempts; timeout 120 seconds;
  concurrency 1.

The ignored run artifacts are coverage-validated and hash-identified as
follows:

| Artifact | SHA-256 |
| --- | --- |
| `predictions.jsonl` | `6482c89ccbac564ff4492ca41d67798cdacb2b11a5a1e81255cedc7dbbce760a` |
| `raw_responses.jsonl` | `19b0b8e7975a9431fed5798074e49306dda8f34eebcb4c8849f2e7b067eb880f` |
| `run_manifest.json` | `1d351e1f8121f1a8dee5c338b17c81b2bb8c9b4222940c7fc387e96b201efa81` |

## Development result

Strict prediction validation passed: 180 expected public IDs, 180 predictions,
no duplicate IDs, no unknown IDs, and no missing IDs. Public development
scoring with `ask.eval.mgp6_v43.score_actions` produced:

| Metric | Value |
| --- | ---: |
| Accuracy | 0.3333 |
| Macro-F1 | 0.1765 |
| Coverage | 1.0000 |
| Selective accuracy | 0.3333 |
| Abstention precision / recall | 0.0000 / 0.0000 |

Prediction counts were KEEP 3, SUPERSEDE 177, and ABSTAIN 0; public dev gold
was exactly balanced at 60 items per action. The resulting confusion matrix
(rows = public development gold; columns = prediction) is:

| Gold \\ Predicted | KEEP | SUPERSEDE | ABSTAIN |
| --- | ---: | ---: | ---: |
| KEEP | 1 | 59 | 0 |
| SUPERSEDE | 1 | 59 | 0 |
| ABSTAIN | 1 | 59 | 0 |

Per-class precision / recall / F1 were KEEP: 0.3333 / 0.0167 / 0.0317;
SUPERSEDE: 0.3333 / 0.9833 / 0.4979; and ABSTAIN: 0.0000 / 0.0000 / 0.0000.

## Operational result

- 180 valid JSON actions; 0 invalid responses, failures, or retries.
- 97,807 prompt tokens and 1,495 completion tokens.
- Wall-clock time: 352.472 seconds.
- Per-call latency (milliseconds): mean 1,954.825; median 1,606.673;
  p95 3,716.818; minimum 853.613; maximum 11,708.743.
- Provider routing and price were not reported by the response metadata, so no
  cost or exact routed-provider claim is made.

Component-cluster confidence intervals are deliberately not computed here. The
component map is a private scoring/audit structure and is not needed for public
development selection. It must be used only by the private final scorer after
fully generated and hashed hidden predictions exist.

## Development decision

This single zero-shot configuration is recorded as a valid development run but
is **not selected** for final hidden evaluation. Its highly skewed action
distribution requires comparison with the pre-registered controller and
ablation configurations before final model, prompt, and system choices are
frozen. No prompt, model, split, or release record was changed as a result of
this run.

The generic v4.3 decision runner now accepts only `decision_zero_shot`. Its
former historical-system labels did not select distinct baseline/controller
implementations, so accepting them would have made a false comparison. The
configuration registry records those systems as requiring explicit, tested v4.3
adapters before they may be run or selected.

The hidden-run authorization remains absent and false.
