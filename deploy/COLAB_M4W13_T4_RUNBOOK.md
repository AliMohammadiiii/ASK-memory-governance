# Colab / T4 runbook, LongMemEval-S 50 controller (Ollama, quality fixes)

This runs the LongMemEval-S 50-session controller evaluation on local Ollama
models on a Colab **T4**, with the 2026-06-08 accuracy + latency fixes enabled
(`deploy/run_colab_m4w13_t4_ollama.sh`, see `FIXES_2026-06-08.md`).

## 1. Upload + unzip

```python
from google.colab import files
uploaded = files.upload()
```

```bash
!unzip -q ask_controller_mgp6_t4_colab_*.zip
%cd ask_controller_mgp6_t4_colab
```

## 2. Run (final, controller, full 50, A10/L4 optimized)

The defaults are already tuned for a 24 GB GPU (A10 / L4). This is the exact
run command:

```bash
!SESSION_WORKERS=3 OLLAMA_NUM_PARALLEL=3 OLLAMA_MAX_LOADED_MODELS=3 \
  EMBEDDER_DEVICE=cuda \
  PROFILE=t4 QUALITY=t4 SYSTEMS=controller \
  bash deploy/run_colab_m4w13_t4_ollama.sh
```

Baked-in defaults: `OLLAMA_MAX_LOADED_MODELS=3`, `OLLAMA_NUM_PARALLEL=3`,
`SESSION_WORKERS=3`, `EMBEDDER_DEVICE=cuda`, `QUALITY=t4` accuracy knobs. The
script also runs cheap computation replay preflight checks before the expensive
LLM evaluation.

### Why these defaults (the slowness fix)

The pipeline interleaves `extraction (llama) -> relation (phi) -> answer (qwen)`
many times per question. With only **one** loaded model, Ollama unload/reloads
on every call, that thrashing, not inference, was the dominant cost on the
first run (~285 s/question with the GPU near 0%). Keeping all three role models
resident kills the thrash, and `SESSION_WORKERS`/`NUM_PARALLEL` fill the idle
GPU with concurrent questions. `EMBEDDER_DEVICE=cuda` moves the MiniLM retrieval
embedder off the 2 CPU cores. `SESSION_WORKERS=3` runs 3 disjoint session shards
as independent processes then merges, per-session grades are identical to
serial, only wall-clock drops.

### Hardware overrides

```bash
# 16 GB T4 (lower parallelism so 3 models + KV cache fit):
!SESSION_WORKERS=2 OLLAMA_NUM_PARALLEL=2 PROFILE=t4 QUALITY=t4 SYSTEMS=controller \
  bash deploy/run_colab_m4w13_t4_ollama.sh
```

If CPU saturates with the workers, raise the CPU reservation to 4 cores, CPU is
cheap next to the GPU, and finishing faster lowers total cost.

What `QUALITY=t4` turns on (T4-affordable levels of the validated knobs):
- `--controller-include-assistant-context`, recovers the ~32% single-session-assistant questions
- `--controller-prior-top-k 3` with `--controller-prior-similarity-threshold 0.45`, lets **Supersede** fire (knowledge-update) while the cosine gate keeps per-question latency bounded
- `--k 10`, `--controller-retrieval-neighbor-window 1`, `--answer-retry-on-unknown`, recall + fewer spurious "Unknown"
- `--controller-temporal-scaffold`, `--controller-computation-answerer`, real question-date scaffolding plus deterministic date/numeric/list answers when evidence is unambiguous

The script installs deps, installs+starts Ollama with the requested loaded-model
and parallelism settings, pulls `qwen3.5:9b`, `llama3.2:3b`, `phi3.5:3.8b`,
runs smoke tests and replay preflight checks, runs the eval, then writes a result
zip whose path it prints at the end.

## 3. If venv creation fails (Colab `ensurepip`)

The script already falls back to Colab's own Python when `.venv` creation fails.
If you prefer to pre-install once and skip the script's install step:

```bash
!rm -rf .venv
!python -m pip install --upgrade pip wheel "setuptools<82"
!python -m pip install -e '.[dev,ml]'
!ASK_INSTALL_DEPS=0 PROFILE=t4 QUALITY=t4 SYSTEMS=controller bash deploy/run_colab_m4w13_t4_ollama.sh
```

## 4. Resuming after a disconnect

Re-run the same command. Finished sessions are skipped and the extraction /
relation / answer caches in `OUT` are reused, so the run continues where it
stopped. Default `OUT=runs/m4w13_50_t4_quality`.

## 5. Useful overrides

```bash
# Re-test only the 15 sessions that were wrong in runs(2).zip:
!SLICE=data/slices/longmemeval_s_cleaned_50_seed0_failed_runs2.jsonl \
  OUT=runs/m4w13_failed_runs2_t4_quality \
  SESSION_WORKERS=3 OLLAMA_NUM_PARALLEL=3 OLLAMA_MAX_LOADED_MODELS=3 \
  EMBEDDER_DEVICE=cuda \
  PROFILE=t4 QUALITY=t4 SYSTEMS=controller \
  bash deploy/run_colab_m4w13_t4_ollama.sh

# Quick 10-session smoke first:
!LIMIT=10 PROFILE=t4 QUALITY=t4 SYSTEMS=controller bash deploy/run_colab_m4w13_t4_ollama.sh

# Skip only the local preflight if you are resuming and already ran it:
!ASK_RUN_PREFLIGHT=0 PROFILE=t4 QUALITY=t4 SYSTEMS=controller bash deploy/run_colab_m4w13_t4_ollama.sh

# Old baseline (no quality knobs), for an A/B against the fixes:
!QUALITY=none PROFILE=t4 SYSTEMS=controller bash deploy/run_colab_m4w13_t4_ollama.sh

# All five systems (slower):
!PROFILE=t4 QUALITY=t4 SYSTEMS=all bash deploy/run_colab_m4w13_t4_ollama.sh
```

Download the printed `RESULT_ZIP` and send it back.
