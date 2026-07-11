#!/usr/bin/env bash
# RUN ONLY — no setup, no pip, no ollama install, no pull, no download.
# Assumes: deps installed, Ollama already serving (deploy/serve.sh), the needed
# models present in Ollama, and the full slice already built (deploy/build_full_slice.sh).
# Safe to run repeatedly; --resume continues an interrupted run.
#
#   WORKERS=4 DATASET=s PROFILE=t4 bash deploy/run_eval.sh
#   SYSTEMS=b4,controller WORKERS=4 bash deploy/run_eval.sh
set -euo pipefail
cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
[ -f .venv/bin/activate ] && source .venv/bin/activate
export PYTHONPATH="src:${PYTHONPATH:-}"

DATASET="${DATASET:-s}"
PROFILE="${PROFILE:-t4}"
SYSTEMS="${SYSTEMS:-all}"
WORKERS="${WORKERS:-4}"
SEED="${SEED:-0}"
SLICE="${SLICE:-data/slices/longmemeval_${DATASET}_full.jsonl}"
OUT="${OUT:-runs/lme_${DATASET}_full_${PROFILE}_seed${SEED}}"

# Preconditions — fail fast with the exact fix, instead of re-doing setup.
[ -f "${SLICE}" ] || { echo "[run] ERROR: slice not found: ${SLICE}"; echo "      build it once:  DATASET=${DATASET} SRC=<cleaned.json> bash deploy/build_full_slice.sh"; exit 1; }
curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 || { echo "[run] ERROR: Ollama not reachable on :11434."; echo "      start it:  WORKERS=${WORKERS} bash deploy/serve.sh"; exit 1; }

# Optional: override the model tags if the ones you imported differ from the
# profile defaults (t4 = qwen3.5:9b / phi3.5:3.8b / llama3.2:3b). e.g.
#   ANSWERER=qwen2.5:7b JUDGE=phi3.5:3.8b bash deploy/run_eval.sh
EXTRA=()
[ -n "${ANSWERER:-}" ]   && EXTRA+=(--answerer-model "${ANSWERER}")
[ -n "${JUDGE:-}" ]      && EXTRA+=(--judge-model "${JUDGE}")
[ -n "${EXTRACTOR:-}" ]  && EXTRA+=(--extractor-model "${EXTRACTOR}")
[ -n "${CLASSIFIER:-}" ] && EXTRA+=(--classifier-model "${CLASSIFIER}")
[ -n "${EMBEDDER:-}" ]   && EXTRA+=(--embedder-model "${EMBEDDER}")

echo "[run] dataset=${DATASET} profile=${PROFILE} systems=${SYSTEMS} workers=${WORKERS} slice=${SLICE}"
python scripts/run_m4w13_ollama.py \
  --model-profile "${PROFILE}" \
  --dataset "${DATASET}" \
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
  ${EXTRA[@]+"${EXTRA[@]}"} \
  --resume

echo "[run] done. Reports: ${OUT}/<system>/report.json"
