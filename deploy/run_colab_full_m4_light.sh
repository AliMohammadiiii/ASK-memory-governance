#!/usr/bin/env bash
set -euo pipefail

PROFILE="${MODEL_PROFILE:-t4}"
SLICE="${1:-/content/longmemeval/longmemeval_s_cleaned.json}"

if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  nohup env OLLAMA_HOST=127.0.0.1:11434 ollama serve > /content/ollama.log 2>&1 &
  sleep 10
fi

python scripts/run_m4w13_ollama.py \
  --model-profile "${PROFILE}" \
  --slice "${SLICE}" \
  --out runs/m4w13 \
  --ollama-host http://127.0.0.1:11434 \
  --ollama-timeout-s "${OLLAMA_TIMEOUT_S:-1800}" \
  --judge-timeout-s "${JUDGE_TIMEOUT_S:-1800}" \
  --embedder-backend ollama

python scripts/summarize_m4w13.py runs/m4w13 \
  --json-out runs/m4w13/summary.json \
  --md-out runs/m4w13/summary.md \
  --require-complete

python scripts/run_mgp6.py \
  --model-profile "${PROFILE}" \
  --systems all \
  --out runs/m4w14 \
  --ollama-host http://127.0.0.1:11434 \
  --ollama-timeout-s "${OLLAMA_TIMEOUT_S:-1800}"

python scripts/run_m4w15.py \
  --model-profile "${PROFILE}" \
  --longmemeval-slice "${SLICE}" \
  --ollama-host http://127.0.0.1:11434 \
  --ollama-timeout-s "${OLLAMA_TIMEOUT_S:-1800}" \
  --judge-timeout-s "${JUDGE_TIMEOUT_S:-1800}" \
  --embedder-backend ollama

python scripts/check_m4w16.py --run-logreg-on-fail

RESULT_ZIP="/content/m4_full_results_$(date +%Y%m%d_%H%M%S).zip"
zip -r "${RESULT_ZIP}" runs NOTES >/dev/null
echo "Results zip: ${RESULT_ZIP}"
