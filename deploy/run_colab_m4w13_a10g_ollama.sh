#!/usr/bin/env bash
set -euo pipefail

# A10G Ollama runner for the M4-W13 LongMemEval controller run.
#
# This is a thin profile-aware wrapper around deploy/run_colab_m4w13_t4_ollama.sh.
# The Ollama runner (scripts/run_m4w13_ollama.py) only understands the model
# profiles {standard, light, t4, thesis} and quality {none, t4}; there is no
# separate "a10g" preset. An A10G (24 GB) is simply a roomier T4: it runs the
# same validated qwen3.5:9b / llama3.2:3b / phi3.5 model set, so this wrapper
# accepts PROFILE=a10g / QUALITY=a10g as aliases for the t4 model set and the
# validated t4 accuracy bundle, sets A10G-appropriate throughput defaults, and
# forwards every extra flag to the Python runner.
#
# Canonical prompt-slim run (default next test — slim, NOT bigger context):
#
#   SLICE=data/slices/longmemeval_s_cleaned_50_seed0_failed_runs4.jsonl \
#   OUT=runs/m4w13_failed_a10g_prompt_slim \
#   SESSION_WORKERS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=3 \
#   EMBEDDER_DEVICE=cuda PROFILE=a10g QUALITY=a10g SYSTEMS=controller \
#   bash deploy/run_colab_m4w13_a10g_ollama.sh \
#     --ollama-num-ctx 32768 \
#     --k 6 \
#     --controller-memory-top-k 20 \
#     --controller-retrieval-neighbor-window 0 \
#     --no-controller-include-assistant-context
#
# The prompt-budget guard in the controller (src/ksa/pipeline/orchestrator.py)
# additionally trims retrieved context so the prompt can never fill num_ctx,
# regardless of the flags above.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

RAW_PROFILE="${PROFILE:-a10g}"
RAW_QUALITY="${QUALITY:-a10g}"

case "${RAW_PROFILE}" in
  a10g) PROFILE=t4 ;;            # a10g shares the t4 Ollama model set
  t4|light) PROFILE="${RAW_PROFILE}" ;;
  *) echo "PROFILE must be a10g|t4|light; got ${RAW_PROFILE}" >&2; exit 2 ;;
esac
case "${RAW_QUALITY}" in
  a10g) QUALITY=t4 ;;            # a10g uses the validated t4 accuracy bundle
  t4|none) QUALITY="${RAW_QUALITY}" ;;
  *) echo "QUALITY must be a10g|t4|none; got ${RAW_QUALITY}" >&2; exit 2 ;;
esac
export PROFILE QUALITY

# A10G (24 GB) throughput defaults. For a deterministic prompt-slim debug run,
# override with SESSION_WORKERS=1 OLLAMA_NUM_PARALLEL=1 (the doc command above).
export SESSION_WORKERS="${SESSION_WORKERS:-3}"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-3}"
export OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS:-3}"
export EMBEDDER_DEVICE="${EMBEDDER_DEVICE:-cuda}"
export OUT="${OUT:-runs/m4w13_failed_a10g_prompt_slim}"

echo "[a10g-ollama] profile=${RAW_PROFILE}->${PROFILE} quality=${RAW_QUALITY}->${QUALITY}" \
     "session_workers=${SESSION_WORKERS} num_parallel=${OLLAMA_NUM_PARALLEL}" \
     "max_loaded=${OLLAMA_MAX_LOADED_MODELS} out=${OUT}" >&2

exec bash "${SCRIPT_DIR}/run_colab_m4w13_t4_ollama.sh" "$@"
