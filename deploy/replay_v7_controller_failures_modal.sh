#!/usr/bin/env bash
# Re-run only the incorrect controller sessions from the v7 stratified run on
# a Modal Endpoint serving Qwen/Qwen3.5-9B via its OpenAI-compatible /v1 API.
set -euo pipefail

cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

: "${MODAL_ENDPOINT_URL:?set MODAL_ENDPOINT_URL to the callable endpoint URL (without /v1)}"
: "${MODAL_KEY:?set MODAL_KEY to the Modal proxy token ID}"
: "${MODAL_SECRET:?set MODAL_SECRET to the Modal proxy token secret}"

PYTHON="${PYTHON:-python3}"
SOURCE_SLICE="${SOURCE_SLICE:-data/slices/longmemeval_m_strat30_seed0.jsonl}"
SOURCE_RUN="${SOURCE_RUN:-runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v7/controller}"
OUT="${OUT:-runs/lme_m_modal_qwen35_9b_v8_v7_failures_nothink}"
FAILED_SLICE="${FAILED_SLICE:-${OUT}/v7_controller_failures.jsonl}"
FAILED_IDS="${FAILED_IDS:-${OUT}/v7_controller_failure_ids.txt}"
MODEL="${MODEL:-Qwen/Qwen3.5-9B}"
SHARDS="${SHARDS:-10}"
EXTRACTION_CONCURRENCY="${EXTRACTION_CONCURRENCY:-1}"
EXTRACTION_MAX_NEW_TOKENS="${EXTRACTION_MAX_NEW_TOKENS:-512}"
RELATION_MAX_NEW_TOKENS="${RELATION_MAX_NEW_TOKENS:-256}"
DRY_RUN="${DRY_RUN:-0}"
PREFLIGHT_RETRIES="${PREFLIGHT_RETRIES:-12}"
PREFLIGHT_DELAY_S="${PREFLIGHT_DELAY_S:-10}"
EMBED_HOST="${EMBED_HOST:-127.0.0.1}"
EMBED_PORT="${EMBED_PORT:-8100}"
EMBED_BASE_URL="${EMBED_BASE_URL:-http://${EMBED_HOST}:${EMBED_PORT}/v1}"
EMBED_MODEL="${EMBED_MODEL:-sentence-transformers/all-MiniLM-L6-v2}"
EMBED_SERVED_NAME="${EMBED_SERVED_NAME:-minilm}"
EMBED_LOG="${EMBED_LOG:-${OUT}/embed_server.log}"
EMBED_READY_RETRIES="${EMBED_READY_RETRIES:-120}"
EMBED_READY_DELAY_S="${EMBED_READY_DELAY_S:-2}"

mkdir -p "${OUT}"
"${PYTHON}" scripts/build_failed_slice_from_run.py \
  --slice "${SOURCE_SLICE}" \
  --run "${SOURCE_RUN}" \
  --out "${FAILED_SLICE}" \
  --ids-out "${FAILED_IDS}"

if [[ "${DRY_RUN}" != "1" ]]; then
  if ! command -v curl >/dev/null 2>&1; then
    echo "[modal-failure-replay] curl is required for the endpoint preflight" >&2
    exit 1
  fi
  models_url="${MODAL_ENDPOINT_URL%/}/v1/models"
  health_body="$(mktemp)"
  health_code=""
  for ((attempt = 1; attempt <= PREFLIGHT_RETRIES; attempt++)); do
    health_code="$(curl --silent --show-error --output "${health_body}" \
      --write-out '%{http_code}' --max-time 60 \
      "${models_url}" \
      -H "Modal-Key: ${MODAL_KEY}" \
      -H "Modal-Secret: ${MODAL_SECRET}" || true)"
    if [[ "${health_code}" == "200" ]]; then
      break
    fi
    echo "[modal-failure-replay] endpoint not ready (HTTP ${health_code:-transport-error}); attempt ${attempt}/${PREFLIGHT_RETRIES}" >&2
    if ((attempt < PREFLIGHT_RETRIES)); then
      sleep "${PREFLIGHT_DELAY_S}"
    fi
  done
  rm -f "${health_body}"
  if [[ "${health_code}" != "200" ]]; then
    echo "[modal-failure-replay] endpoint preflight failed: ${models_url} returned HTTP ${health_code:-transport-error}" >&2
    exit 1
  fi
  echo "[modal-failure-replay] endpoint healthy: ${models_url}"
fi

# Ten local sentence-transformer copies can crash the macOS process group while
# loading native Torch/tokenizer state (observed exit -11 before any prediction).
# Keep ten controller shards, but route them through one shared MiniLM server.
embed_pid=""
cleanup() {
  if [[ -n "${embed_pid}" ]]; then
    kill "${embed_pid}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ "${DRY_RUN}" != "1" ]]; then
  embed_health_url="${EMBED_BASE_URL%/v1}/health"
  embed_server_model() {
    curl --silent --show-error --fail --max-time 5 "${embed_health_url}" 2>/dev/null \
      | "${PYTHON}" -c 'import json, sys; print(json.load(sys.stdin).get("model", ""))' \
      2>/dev/null
  }
  current_embed_model="$(embed_server_model || true)"
  if [[ -n "${current_embed_model}" && "${current_embed_model}" != "${EMBED_SERVED_NAME}" ]]; then
    echo "[modal-failure-replay] ${EMBED_BASE_URL} serves '${current_embed_model}', expected '${EMBED_SERVED_NAME}'; choose another EMBED_PORT" >&2
    exit 1
  fi
  if [[ "${current_embed_model}" == "${EMBED_SERVED_NAME}" ]]; then
    echo "[modal-failure-replay] reusing embed server: ${EMBED_BASE_URL}"
  else
    echo "[modal-failure-replay] starting shared embed server: ${EMBED_MODEL}"
    {
      printf '[modal-failure-replay] embed command:'
      printf ' %q' "${PYTHON}" scripts/serve_embeddings.py \
        --model "${EMBED_MODEL}" --served-name "${EMBED_SERVED_NAME}" \
        --device cpu --trust-remote-code --batch-size 128 --max-seq-length 256 \
        --host "${EMBED_HOST}" --port "${EMBED_PORT}"
      printf '\n\n'
    } >> "${EMBED_LOG}"
    "${PYTHON}" scripts/serve_embeddings.py \
      --model "${EMBED_MODEL}" \
      --served-name "${EMBED_SERVED_NAME}" \
      --device cpu \
      --trust-remote-code \
      --batch-size 128 \
      --max-seq-length 256 \
      --host "${EMBED_HOST}" \
      --port "${EMBED_PORT}" >> "${EMBED_LOG}" 2>&1 &
    embed_pid="$!"

    embed_ready="0"
    for ((attempt = 1; attempt <= EMBED_READY_RETRIES; attempt++)); do
      current_embed_model="$(embed_server_model || true)"
      if [[ "${current_embed_model}" == "${EMBED_SERVED_NAME}" ]]; then
        embed_ready="1"
        break
      fi
      if ! kill -0 "${embed_pid}" >/dev/null 2>&1; then
        echo "[modal-failure-replay] embed server exited during startup; see ${EMBED_LOG}" >&2
        exit 1
      fi
      sleep "${EMBED_READY_DELAY_S}"
    done
    if [[ "${embed_ready}" != "1" ]]; then
      echo "[modal-failure-replay] embed server did not become healthy; see ${EMBED_LOG}" >&2
      exit 1
    fi
    echo "[modal-failure-replay] embed server healthy: ${EMBED_BASE_URL}"
  fi
fi

# Modal Endpoint auth is supplied automatically by the OpenAI-compatible
# client from MODAL_KEY/MODAL_SECRET. Empty provider bodies avoid sending
# OpenRouter-specific routing fields to Modal.
cascade_cmd=(
  "${PYTHON}" scripts/run_vllm_cascade.py
  --slice "${FAILED_SLICE}"
  --out "${OUT}"
  --systems controller
  --shards "${SHARDS}"
  --fast-base-url "${MODAL_ENDPOINT_URL%/}/v1"
  --big-base-url "${MODAL_ENDPOINT_URL%/}/v1"
  --fast-model "${MODEL}"
  --big-model "${MODEL}"
  --openai-api-key-env MODAL_DUMMY_API_KEY
  --openai-extra-body-json '{}'
  --openai-chat-template-kwargs-json '{"enable_thinking":false}'
  --openai-max-model-len 32768
  --extraction-concurrency "${EXTRACTION_CONCURRENCY}"
  --extraction-max-new-tokens "${EXTRACTION_MAX_NEW_TOKENS}"
  --relation-max-new-tokens "${RELATION_MAX_NEW_TOKENS}"
  --embed-base-url "${EMBED_BASE_URL}"
  --embed-model "${EMBED_SERVED_NAME}"
  --embed-batch-size 128
  --judge same_as_answerer
  --v8-fixes
  --no-escalation
  --shard-retries 2
  --shard-retry-backoff-s 5
)
if [[ "${DRY_RUN}" == "1" ]]; then
  cascade_cmd+=(--dry-run)
fi
"${cascade_cmd[@]}"

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "[modal-failure-replay] dry run complete; no report was generated"
else
  echo "[modal-failure-replay] report: ${OUT}/controller/report.json"
fi
echo "[modal-failure-replay] ids: ${FAILED_IDS}"
