# M4-W13 LongMemEval-S Final Policy

Status date: 2026-07-07

The core final-candidate LongMemEval-S run is defined in
`configs/eval_longmemeval_final.yaml`.

## Policy

- Dataset: `data/slices/longmemeval_s_cleaned_50_seed0.jsonl`.
- Systems: B1 no-memory, B2 flat-vector, B3 recency, B4 naive-overwrite, and controller.
- Judge tier: Ollama `phi3.5:3.8b`.
- Model profile: `thesis`.
- Raw-turn fallback: disabled.
- Thesis use: final-candidate pending review after completion.

## Current Status

The full all-system final-candidate run is still incomplete. Later partial
Ollama thesis-profile runs produced accepted B1/B2/B3 artifacts under
`runs/m4w13_50_llama/`; see `NOTES/m4w13_50_llama_b1_b2_b3_audit.md`.

Accepted partial LongMemEval-S 50-item baseline results:

| System | Baseline | n | Accuracy | 95% CI | Status |
|---|---|---:|---:|---|---|
| B1 | no-memory | 50 | 18.0% | 8.0%-30.0% | accepted; do not rerun |
| B2 | flat-vector | 50 | 38.0% | 24.0%-52.0% | accepted; do not rerun |
| B3 | recency | 50 | 22.0% | 10.0%-34.0% | accepted; do not rerun |

Remaining systems for the matched all-system comparison are B4 and the
controller. No B4/controller final-candidate output is accepted in this
workspace as of 2026-07-07. The existing `runs/m4w13_light_smoke/` directory
remains smoke evidence only (`limit=2`). The older planned target
`runs/m4w13_final_candidate/` remains pending unless the final artifact is
standardized under `runs/m4w13_50_llama/`.

## Continuation Command

Use this command only after restoring the accepted `b1`, `b2`, and `b3`
directories from `artifacts/m4w13_50_llama/runs(2).zip` and
`artifacts/m4w13_50_llama/runs(3).zip` into `runs/m4w13_50_llama/`.

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
