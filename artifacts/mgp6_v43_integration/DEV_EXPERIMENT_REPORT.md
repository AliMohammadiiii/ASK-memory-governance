# MGP-6 v4.3 development experiment report

## Scope and boundary

This records completed development-only evaluations of `decision_zero_shot`,
B1--B4, `live_model_controller`, and the deterministic `rules_controller`.
Each used only the public 180-record development split and public development
labels. None read hidden inputs, hidden gold, final human gold, private
mappings, or audit records. These are not final hidden results and must not be
reported as real-world generalization.

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

## B2--B4 model-backed baseline results

B2 (flat retrieval), B3 (recency), and B4 (overwrite) completed on the public
dev split. Their manifests each record commit
`ff33594e73f46e1b9d6281ea7ec5b90ee2960d17`, a clean tracked worktree, the
same public dataset hash, the Qwen/OpenRouter model ID, seed 4301, temperature
0.0, 128 maximum new tokens, `reasoning.effort=none`, and
`hidden_gold_accessed=false`. All three passed strict coverage validation with
180 valid JSON predictions and zero failures, retries, or invalid responses.

| System | Accuracy | Macro-F1 | KEEP / SUPERSEDE / ABSTAIN | Prompt / completion tokens | Mean / p95 latency (ms) | Wall time (s) |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| B2 flat retrieval | 0.3556 | 0.2380 | 7 / 165 / 8 | 107,374 / 1,426 | 2,685.372 / 6,272.670 | 484.539 |
| B3 recency | 0.3389 | 0.2309 | 9 / 157 / 14 | 41,863 / 1,422 | 2,796.578 / 8,643.082 | 504.038 |
| B4 overwrite | 0.3444 | 0.2064 | 11 / 169 / 0 | 104,107 / 1,418 | 3,009.834 / 10,459.101 | 542.411 |

Per-class F1 (KEEP / SUPERSEDE / ABSTAIN) was 0.0896 / 0.5067 / 0.1176 for B2,
0.0870 / 0.4977 / 0.1081 for B3, and 0.1127 / 0.5066 / 0.0000 for B4. B4's
zero ABSTAIN predictions are consistent with its pre-registered two-action
constraint. The public scorer did not read the private component map, so no
component-cluster intervals are presented. Provider routing and price were not
reported; no cost claim is made.

The ignored artifact hashes are recorded for replay: B2 prediction/raw/manifest
SHA-256 values are `7bdbdecead66a15638c7b299df5163217035ceea73df2e877c0995528e362a78`,
`3fc8873750f9b623f5fa45ed353c1a547d7835aeab974097d0f4fce468a68c52`, and
`3e549e632cf9c1568214970f4a73b6dbd0356610959348d40d2416c13a625a90`;
B3's are `eac02f8aa27abefc91886c32ee86b1050335757586aaab4b358e1af17bffe2f6`,
`453f2b3b347d948ea2b38be0c69272110f484fafec0c7cd0969c26c02edd435e`, and
`f97a10ce94ecef09886ebc5e99c151cc853ea348cb49c471dc8efd2ea3850419`;
B4's are `f296cb1ce580feccfff4124c4b607aa893583094dd24ae0ed12cce9dd8fe8950`,
`687ecabcd98017a7ae5f9d6e77c56d7a5af4126385773afe10d476251f74ba5b`, and
`551c29dc050bf3bee51cbe616fe6d411e7992079a7d5408b137ada2f02a354bd`.

## Live-model controller development result

The ASK `live_model_controller` completed public development using the
controller-policy prompt and full public model view. Its manifest records commit
`b5a6c602492c2bbcc8dd688371bd4f8d08556e03`, a clean tracked worktree, seed
4301, temperature 0.0, 128 maximum new tokens, `reasoning.effort=none`, and
`hidden_gold_accessed=false`. The prompt and system-prompt hashes are
`51ba5ad47be71d5b6c2cf007e5eac1e119d3796f0a7dd0e393cce454af83bb72` and
`7d13392e9e4a0acba3ef2611872834df64d87fc7823cf8dfa12357df1969852d`.

Strict validation passed: 180 expected IDs, 180 predictions, no duplicate,
unknown, or missing public IDs, and zero invalid responses, failures, or
retries. Accuracy was 0.3333, Macro-F1 0.1771, coverage 1.0000, selective
accuracy 0.3333, and abstention precision/recall 0.0000/0.0000. It predicted
KEEP 4, SUPERSEDE 176, and ABSTAIN 0. Per-class F1 (KEEP / SUPERSEDE / ABSTAIN)
was 0.0313 / 0.5000 / 0.0000.

The run used 109,147 prompt tokens and 1,432 completion tokens. Wall-clock time
was 527.952 seconds; mean/median/p95 request latency was 2,929.495 / 1,856.621
/ 8,537.174 ms. No provider routing or price was returned, and no cost claim is
made. The public scorer did not read the private component map, so it did not
compute component-cluster intervals. Ignored prediction/raw/manifest SHA-256
values are `5f2dde4e824aef39f7ed5dee000e7aab8a1994154a4b104d527f39b765fa1f76`,
`63a0c48138773d308a200b20041c620336385df979d526e7efd8abfda2033b39`, and
`45790c3f1c705c061e4adb811bb67343a34a5b6ea3442b1a4e3f7b2dd6709ced`.

## Development decision

The zero-shot, B1--B4, live-model-controller, and rules-controller
configurations are valid development runs but are **not selected** for final
hidden evaluation. Their distributions and metrics require comparison with the
remaining pre-registered ablations before model, prompt, and system choices are
frozen. No prompt, model, split, or release record was changed as a result of
these runs.

## Rules-controller development result

After the system-adapter implementation commit
`c37b8878512cd4125a4beb793dd2a6625c35a9df`, the deterministic ASK scorecard
rules controller completed all 180 public dev records. It produced 180 valid
predictions with zero failures, retries, invalid responses, provider calls, or
hidden-gold access; its manifest records a clean tracked worktree. Accuracy was
0.3333, Macro-F1 was 0.2434, coverage was 1.0000, and its predictions were
KEEP 0, SUPERSEDE 39, ABSTAIN 141. It is not selected for hidden evaluation.

The generic-label ambiguity is resolved: B1--B4, both controller modes, and
the required ablations now have explicit v4.3 adapter contracts. B1--B4 and
both controller modes have completed; the four model-backed ablations remain
pending. See `ADAPTER_IMPLEMENTATION_REPORT.md`.

The hidden-run authorization remains absent and false.
