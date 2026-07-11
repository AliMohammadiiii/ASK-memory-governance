#!/usr/bin/env bash
set -euo pipefail

PROFILE="${MODEL_PROFILE:-t4}"
SLICE="${1:-/content/longmemeval/longmemeval_s_cleaned.json}"
OUT="${2:-runs/m4w13}"

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
  --out "${OUT}" \
  --ollama-host http://127.0.0.1:11434 \
  --ollama-timeout-s "${OLLAMA_TIMEOUT_S:-1800}" \
  --judge-timeout-s "${JUDGE_TIMEOUT_S:-1800}" \
  --embedder-backend ollama

python scripts/summarize_m4w13.py "${OUT}" \
  --json-out "${OUT}/summary.json" \
  --md-out "${OUT}/summary.md" \
  --require-complete

RESULT_ZIP="/content/m4w13_results_$(date +%Y%m%d_%H%M%S).zip"
zip -r "${RESULT_ZIP}" "${OUT}" >/dev/null
echo "Results zip: ${RESULT_ZIP}"
