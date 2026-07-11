# LongMemEval-S 50 B4 + Controller TODO

Status:
blocked; B4 naive-overwrite and controller are not complete in this workspace.

Why blocked:
Ollama is installed at `/opt/homebrew/bin/ollama`, but no server is listening on
`http://127.0.0.1:11434` during this repair pass. The continuation run requires
the thesis-profile Ollama models and a running Ollama service.

Exact command to run:

```bash
source .venv/bin/activate
python scripts/run_m4w13_ollama.py \
  --model-profile thesis \
  --slice data/slices/longmemeval_s_cleaned_50_seed0.jsonl \
  --out runs/m4w13_50_llama \
  --systems b4,controller \
  --seed 0 \
  --n-bootstrap 1000 \
  --ollama-host http://127.0.0.1:11434 \
  --ollama-timeout-s 1800 \
  --judge-timeout-s 1800 \
  --embedder-backend sentence_transformer \
  --controller-include-assistant-context \
  --session-workers 2
```

Required inputs:
- `data/slices/longmemeval_s_cleaned_50_seed0.jsonl`
- `configs/eval_longmemeval_final.yaml`
- `configs/controller_active.yaml`
- accepted restored B1/B2/B3 outputs or their provenance zips
- running Ollama service with thesis-profile models from `deploy/pull_models.sh`

Expected outputs:
- `runs/m4w13_50_llama/b4/report.json`
- `runs/m4w13_50_llama/b4/results.md`
- `runs/m4w13_50_llama/controller/report.json`
- `runs/m4w13_50_llama/controller/results.md`
- `runs/m4w13_50_llama/summary.json`
- `runs/m4w13_50_llama/summary.md`
- promotion-gate output from `scripts/promote_lme_to_final.py`

Accepted B1/B2/B3 paths:
- `artifacts/m4w13_50_llama/runs(2).zip`
- `artifacts/m4w13_50_llama/runs(3).zip`
- restored local `runs/m4w13_50_llama/b1/report.json`
- restored local `runs/m4w13_50_llama/b2/report.json`
- restored local `runs/m4w13_50_llama/b3/report.json`

Missing B4 output path:
- `runs/m4w13_50_llama/b4/report.json`
- `runs/m4w13_50_llama/controller/report.json`

Estimated runtime if known:
unknown on this machine; treat as a multi-hour model-backed run.

How to update manifest after completion:
1. Run `scripts/summarize_m4w13.py runs/m4w13_50_llama --systems all --require-complete`
   with JSON/Markdown outputs under `runs/m4w13_50_llama/`.
2. Run `scripts/promote_lme_to_final.py` and record the verdict.
3. Update `ARTIFACT_MANIFEST.md` from `partial` to the actual gate status only
   if the five-system summary succeeds.
4. Update `FINAL_OK.json` from `partial_ok` to `final_ok` only if all final
   evidence conditions are satisfied.
