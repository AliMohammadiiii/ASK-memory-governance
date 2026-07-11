#!/usr/bin/env bash
# Run all five memory systems on the FULL 500-question LongMemEval set
# (S or M), via local Ollama. This is the scale-up of the M4-W13 50-question
# dev slice to the full benchmark recommended by the benchmark analysis.
#
# Usage:
#   bash deploy/run_colab_lme_full.sh <s|m> [model_profile] [systems]
#
#   <s|m>          : dataset family. 's' = LongMemEval-S (~115k-token haystacks),
#                    'm' = LongMemEval-M (~500-session haystacks).
#   [model_profile]: thesis (default; final-candidate tier) | t4 | light | standard
#   [systems]      : 'all' (default) or e.g. 'b1,b2,controller'
#
# Env overrides: SLICE, OUT, OLLAMA_TIMEOUT_S, JUDGE_TIMEOUT_S, SESSION_WORKERS,
#                K, NUM_CTX, SEED.
set -euo pipefail

DS="${1:?usage: bash deploy/run_colab_lme_full.sh <s|m> [profile] [systems]}"
PROFILE="${2:-thesis}"
SYSTEMS="${3:-all}"
SEED="${SEED:-0}"

case "${DS}" in
  s) DEFAULT_SRC="/content/longmemeval/longmemeval_s_cleaned.json" ;;
  m) DEFAULT_SRC="/content/longmemeval/longmemeval_m_cleaned.json" ;;
  *) echo "dataset must be 's' or 'm'"; exit 2 ;;
esac

SRC="${SRC:-${DEFAULT_SRC}}"
SLICE="${SLICE:-data/slices/longmemeval_${DS}_full.jsonl}"
OUT="${OUT:-runs/lme_${DS}_full_${PROFILE}_seed${SEED}}"

if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi
export PYTHONPATH="src:${PYTHONPATH:-}"

# 1) Build the full 500-question slice (no sampling, deterministic id order).
#    For LongMemEval-M this streams the large JSON array (ijson) and writes a
#    memory-light JSONL that every later run/resume reads cheaply.
if [ ! -f "${SLICE}" ]; then
  echo "[full] building full slice from ${SRC} -> ${SLICE}"
  python scripts/build_slice.py --in "${SRC}" --out "${SLICE}" --n all
fi

# 2) Make sure an Ollama daemon is up — started WITH the parallelism env so the
#    server actually serves concurrent requests. A client-side env alone does
#    not change a running server, so the daemon must be (re)started with these.
#    OLLAMA_NUM_PARALLEL defaults to SESSION_WORKERS; bump both together.
WORKERS="${SESSION_WORKERS:-1}"
NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-${WORKERS}}"
MAX_LOADED="${OLLAMA_MAX_LOADED_MODELS:-2}"
if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  nohup env OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_NUM_PARALLEL="${NUM_PARALLEL}" \
    OLLAMA_MAX_LOADED_MODELS="${MAX_LOADED}" \
    ollama serve > /content/ollama.log 2>&1 &
  sleep 10
  echo "[full] ollama serve started: OLLAMA_NUM_PARALLEL=${NUM_PARALLEL} OLLAMA_MAX_LOADED_MODELS=${MAX_LOADED}"
else
  echo "[full] NOTE: an Ollama server is already running; for ${NUM_PARALLEL}-way"
  echo "       parallelism restart it with OLLAMA_NUM_PARALLEL=${NUM_PARALLEL}."
fi

# 3) Run the suite on the full set. --dataset stamps S/M provenance in the
#    manifest so an M run is never mislabeled S. Memory systems retrieve top-k,
#    so the answer prompt size is bounded by k (not the haystack) — the default
#    8k context is fine even for M; the per-question cost on M is ingestion.
python scripts/run_m4w13_ollama.py \
  --model-profile "${PROFILE}" \
  --dataset "${DS}" \
  --systems "${SYSTEMS}" \
  --slice "${SLICE}" \
  --out "${OUT}" \
  --seed "${SEED}" \
  --ollama-host http://127.0.0.1:11434 \
  --ollama-timeout-s "${OLLAMA_TIMEOUT_S:-1800}" \
  --judge-timeout-s "${JUDGE_TIMEOUT_S:-1800}" \
  --embedder-backend ollama \
  --k "${K:-5}" \
  --ollama-num-ctx "${NUM_CTX:-8192}" \
  --session-workers "${WORKERS}" \
  --resume

echo "[full] done. Reports under ${OUT}/<system>/report.json"
echo "[full] each report.json now carries answerable_accuracy / abstention_accuracy / n_degenerate_answers."
