# M4-W13 Runs

Date: 2026-05-21

Update 2026-06-02: B1/B2/B3 from partial Ollama thesis-profile 50-item runs
`runs/m4w13_50_llama/` were audited and accepted. See
`NOTES/m4w13_50_llama_b1_b2_b3_audit.md`. Do not rerun those three baselines
unless the protocol changes; the remaining systems are B4 and controller.

## Scope

This run package executes the five required systems:

- `b1` = no-memory
- `b2` = flat-vector
- `b3` = recency-pruning with the M2 LLM extractor
- `b4` = naive-overwrite
- `controller` = scorecard controller

Outputs are written as:

```text
runs/m4w13/{b1,b2,b3,b4,controller}/report.json
runs/m4w13/{b1,b2,b3,b4,controller}/predictions.jsonl
```

`answers.jsonl` is still written for backward compatibility with M1-M3 notes.

## Original Command

This is the original M4-W13 command for `runs/m4w13/`. For the accepted
`runs/m4w13_50_llama/` B1/B2/B3 partial artifacts, use the continuation command
in `NOTES/m4w13_50_llama_b1_b2_b3_audit.md` and do not include B1/B2/B3 again.

```bash
source .venv/bin/activate

python scripts/run_m4w13_ollama.py \
  --slice /Users/ali/Downloads/longmemeval/longmemeval_s_cleaned.json \
  --out runs/m4w13 \
  --model-profile light \
  --ollama-host http://localhost:11434 \
  --ollama-timeout-s 1800 \
  --judge-timeout-s 1800 \
  --seed 0 \
  --n-bootstrap 1000

python scripts/summarize_m4w13.py runs/m4w13 \
  --json-out runs/m4w13/summary.json \
  --md-out runs/m4w13/summary.md
```

For a dry command audit:

```bash
python scripts/run_m4w13_ollama.py --dry-run
```

For the local six-model answerer sweep:

```bash
python scripts/run_m4w13_ollama.py --model-sweep
```

The sweep writes to `runs/m4w13/by_answerer/<model>/...` and is a model
robustness run, not the controlled five-system comparison.

## Current Status

The code now validates the requested Ollama model pool before running. On this
machine, the requested tags are installed:

- `gemma4:e4b`
- `gemma4:e2b`
- `qwen3.5:9b`
- `llama3.2:3b`
- `phi3.5:3.8b`
- `phi4:14b`

The real public cleaned S split is available locally at
`/Users/ali/Downloads/longmemeval/longmemeval_s_cleaned.json` and contains 500
questions. A real 50-question smoke slice was generated at
`data/slices/longmemeval_s_cleaned_50_seed0.jsonl`.

The checked-in `data/longmemeval_s_synthetic.jsonl` can still be used for
pipeline validation, but not for Chapter 4 publication results.

`--model-profile light` uses `llama3.2:3b` for answer/extraction/retrieval
embeddings and `phi3.5:3.8b` for judge/classification. The M4-W13 Ollama
runner defaults retrieval embeddings to Ollama `/api/embed`, avoiding the
Apple-Silicon `sentence-transformers`/libomp crash path. Use the default
standard profile only when you want the heavier `gemma4:e4b` / `phi4:14b` run.

## Metrics

`report.json` carries overall and per-competency accuracy with bootstrap 95%
CIs. `scripts/summarize_m4w13.py` adds:

- SMRR: `stale_retrieval_count / retrieved_items`
- current-session leakage count
- wall-clock seconds per system

B3, B4, and controller now emit explicit `stale_retrieval_count` and
`smrr_denominator` telemetry in `predictions.jsonl`.
