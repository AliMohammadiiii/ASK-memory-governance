#!/usr/bin/env bash
set -euo pipefail

SYSTEM="${1:?usage: bash deploy/run_colab_m4w13_one_system.sh <b1|b2|b3|b4|controller> [slice] [out]}"
PROFILE="${MODEL_PROFILE:-t4}"
SLICE="${2:-/content/longmemeval/longmemeval_s_cleaned.json}"
OUT="${3:-runs/m4w13}"

if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  nohup env OLLAMA_HOST=127.0.0.1:11434 ollama serve > /content/ollama.log 2>&1 &
  sleep 10
fi

python scripts/run_m4w13_ollama.py \
  --model-profile "${PROFILE}" \
  --systems "${SYSTEM}" \
  --slice "${SLICE}" \
  --out "${OUT}" \
  --ollama-host http://127.0.0.1:11434 \
  --ollama-timeout-s "${OLLAMA_TIMEOUT_S:-1800}" \
  --judge-timeout-s "${JUDGE_TIMEOUT_S:-1800}" \
  --embedder-backend ollama

RESULT_ZIP="/content/m4w13_${SYSTEM}_$(date +%Y%m%d_%H%M%S).zip"
zip -r "${RESULT_ZIP}" "${OUT}" >/dev/null
echo "Results zip: ${RESULT_ZIP}"
