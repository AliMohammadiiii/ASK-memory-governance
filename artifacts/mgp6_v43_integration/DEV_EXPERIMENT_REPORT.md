# MGP-6 v4.3 development experiment report

## Scope and boundary

This records completed development-only evaluations of `decision_zero_shot`,
`b1` (no-memory), and the deterministic `rules_controller`. Each used only the
public 180-record development split and public development labels. None read
hidden inputs, hidden gold, final human gold, private mappings, or audit
records. These are not final hidden results and must not be reported as
real-world generalization.

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

## B1 no-memory development result

The first model-backed baseline adapter, `b1`, completed against the same public
development split after the adapter implementation was committed:

```text
.venv/bin/python scripts/run_mgp6_v43.py \
  --input benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl \
  --out runs/mgp6_v43/dev/b1_qwen35_9b \
  --system b1 \
  --provider openrouter \
  --base-url https://openrouter.ai/api/v1 \
  --api-key-env OPENROUTER_API_KEY \
  --model-id qwen/qwen3.5-9b \
  --seed 4301 \
  --max-new-tokens 128 \
  --reasoning-effort none \
  --parse-retry-max-attempts 2
```

- Run commit: `e309893a7e643baa1d5a409d665c49656ceb977e`; the manifest records
  a clean tracked worktree.
- Adapter: `ask.mgp6_v43_adapter.v1`; dialogue/query only, with
  `memory_before` omitted.
- Prompt hash: `28bfbff2decc989b60ef7c84dc959bfc1fbda92426e1754a374f22755cc847fb`.
- System-prompt hash:
  `13c6841f8e380358a3054e6f243bcdfa718fce744d587c294275266952f286e0`.
- Prediction SHA-256:
  `1e2212cf6a8b6e1919222e39a16d88aa1ddbcf9b17b7471dbfcb94dd4a50de2e`.
- Raw-response SHA-256:
  `1dbd379607d2d7ef2d262eb2637f97d967f0d023df2b3c001a4e9cf53ed08cf2`.
- Manifest SHA-256:
  `508eb339117bfdc68e7745a7f3557f56cf1d75350ad15b81260be9e0d6bb5ee0`.

Strict validation passed: 180 expected public IDs, 180 predictions, and no
duplicates, unknown IDs, or omissions. Public-dev metrics were accuracy 0.3667,
Macro-F1 0.3150, coverage 1.0000, selective accuracy 0.3630, and abstention
precision/recall 0.3824/0.2167. Prediction counts were KEEP 13, SUPERSEDE 133,
and ABSTAIN 34. Per-class precision / recall / F1 were KEEP: 0.5385 / 0.1167 /
0.1918; SUPERSEDE: 0.3459 / 0.7667 / 0.4767; and ABSTAIN: 0.3824 / 0.2167 /
0.2766.

The run returned 180 valid JSON actions with zero invalid responses, failures,
or retries, using 102,091 prompt tokens and 1,414 completion tokens. Wall-clock
time was 449.747 seconds; mean/median/p95 request latency was 2,493.892 /
1,938.197 / 5,908.991 ms. Provider routing and price were not returned, so no
cost or routed-provider claim is made. `hidden_gold_accessed=false`; the public
scorer did not read the private component map and did not compute component
intervals.

## Development decision

The zero-shot, B1, and rules-controller configurations are valid development
runs but are **not selected** for final hidden evaluation. Their distributions
and metrics require comparison with the remaining pre-registered systems before
model, prompt, and system choices are frozen. No prompt, model, split, or
release record was changed as a result of these runs.

## Rules-controller development result

After the system-adapter implementation commit
`c37b8878512cd4125a4beb793dd2a6625c35a9df`, the deterministic ASK scorecard
rules controller completed all 180 public dev records. It produced 180 valid
predictions with zero failures, retries, invalid responses, provider calls, or
hidden-gold access; its manifest records a clean tracked worktree. Accuracy was
0.3333, Macro-F1 was 0.2434, coverage was 1.0000, and its predictions were
KEEP 0, SUPERSEDE 39, ABSTAIN 141. It is not selected for hidden evaluation.

The generic-label ambiguity is resolved: B1--B4, both controller modes, and
the required ablations now have explicit v4.3 adapter contracts. B1 has now
completed; B2--B4, the live-model controller, and the four model-backed
ablations remain pending. See `ADAPTER_IMPLEMENTATION_REPORT.md`.

The hidden-run authorization remains absent and false.
