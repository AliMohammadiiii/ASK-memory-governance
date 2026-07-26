# Post-final MGP-6 successor candidate

This directory records work performed after the single authorized MGP-6 v4.3
hidden experiment was completed. The candidate is intentionally restricted to
public train/dev inputs. The runner rejects `--hidden-input` for this system.

The successor adds an explicit evidence decision order (scope, conditions,
persistence, and ordered settings) and a public-development-informed,
high-confidence guard. It contains no public-ID table and no private fields.

Replaying the guard over the recorded public dev model outputs changes 26 of
180 predictions and scores 1.000 accuracy / 1.000 macro-F1. This is a dev replay,
not a fresh model run, and must not be presented as confirmatory performance.
A fresh dev run is still required to verify end-to-end model behavior. Any
claim beyond public development additionally requires a new independent
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
