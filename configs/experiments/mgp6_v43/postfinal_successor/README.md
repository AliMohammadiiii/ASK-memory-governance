# Post-final MGP-6 successor candidate

This directory records work performed after the single authorized MGP-6 v4.3
hidden experiment was completed. The candidate is intentionally restricted to
public train/dev inputs. The runner rejects `--hidden-input` for this system.

The successor adds an explicit evidence decision order (scope, conditions,
persistence, and ordered settings) and a public-development-informed,
high-confidence guard. It contains no public-ID table and no private fields.

The initial retrospective replay over the historical public dev outputs scored
1.000 accuracy / 1.000 macro-F1. A subsequent fresh 180-item Qwen generation
exposed a guard-composition bug: the successor guard replaced rather than
followed the v3 conservative guard. Commit `e6eab00` fixes that composition.
Deterministically reapplying the corrected adapter to the sealed fresh model
responses scores 0.9611 accuracy and 0.9607 macro-F1 with complete coverage.
The hashes and confusion matrix are recorded in `FRESH_PUBLIC_DEV_RESULT.json`.

This remains a dev-informed public-development result, not confirmatory
performance. Any claim beyond public development requires a new independent
component-held-out set; the completed v4.3 hidden set cannot be reused.

Run the fresh public dev candidate with:

```bash
.venv/bin/python scripts/run_mgp6_v43.py \
  --input benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl \
  --out runs/mgp6_v43/postfinal_successor/dev_qwen35_9b \
  --system successor_live_model_controller \
  --provider openrouter \
  --base-url https://openrouter.ai/api/v1 \
  --api-key-env OPENROUTER_API_KEY \
  --model-id qwen/qwen3.5-9b \
  --seed 4301 \
  --max-new-tokens 128 \
  --reasoning-effort none \
  --parse-retry-max-attempts 2
```

Then score only the public dev labels:

```bash
.venv/bin/python scripts/score_mgp6_v43.py \
  --input benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl \
  --predictions runs/mgp6_v43/postfinal_successor/dev_qwen35_9b/predictions.jsonl \
  --raw-responses runs/mgp6_v43/postfinal_successor/dev_qwen35_9b/raw_responses.jsonl \
  --run-manifest runs/mgp6_v43/postfinal_successor/dev_qwen35_9b/run_manifest.json \
  --out runs/mgp6_v43/postfinal_successor/dev_qwen35_9b/public_dev_metrics.json
```
