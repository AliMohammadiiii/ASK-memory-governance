#!/usr/bin/env bash
set -euo pipefail

SLICE="${1:-/content/longmemeval/longmemeval_s_cleaned.json}"
OUT="${2:-runs/m4w13_hf}"
LIMIT="${LIMIT:-35}"
EMBEDDER_DEVICE="${EMBEDDER_DEVICE:-auto}"
CONTROLLER_MEMORY_TOP_K="${CONTROLLER_MEMORY_TOP_K:-32}"

if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

python scripts/run_m4w13_hf.py \
  --systems controller \
  --limit "${LIMIT}" \
  --slice "${SLICE}" \
  --out "${OUT}" \
  --embedder-device "${EMBEDDER_DEVICE}" \
  --controller-memory-top-k "${CONTROLLER_MEMORY_TOP_K}"

RESULT_ZIP="/content/m4w13_hf_controller_$(date +%Y%m%d_%H%M%S).zip"
zip -r "${RESULT_ZIP}" "${OUT}" >/dev/null
echo "Results zip: ${RESULT_ZIP}"
