#!/usr/bin/env bash
set -euo pipefail

SLICE="${SLICE:-/content/longmemeval/longmemeval_s_cleaned.json}"
OUT="${OUT:-runs/m4w13_a100_50}"
SYSTEMS="${SYSTEMS:-all}"
LIMIT="${LIMIT-50}"
MAX_WORKERS="${MAX_WORKERS:-2}"
STATUS_S="${STATUS_S:-30}"
EMBEDDER_DEVICE="${EMBEDDER_DEVICE:-auto}"
QUALITY_PRESET="${QUALITY_PRESET:-none}"
HF_MODEL="${HF_MODEL:-Qwen/Qwen2.5-3B-Instruct}"
HF_MAX_SEQ_LEN="${HF_MAX_SEQ_LEN:-4096}"
RETRIEVAL_K="${RETRIEVAL_K:-5}"
CONTROLLER_MEMORY_TOP_K="${CONTROLLER_MEMORY_TOP_K:-32}"
RECENCY_MEMORY_TOP_K="${RECENCY_MEMORY_TOP_K:-32}"
EXTRACTION_MAX_NEW_TOKENS="${EXTRACTION_MAX_NEW_TOKENS:-192}"
RELATION_MAX_NEW_TOKENS="${RELATION_MAX_NEW_TOKENS:-96}"
CONTROLLER_RETRIEVAL_NEIGHBOR_WINDOW="${CONTROLLER_RETRIEVAL_NEIGHBOR_WINDOW:-0}"
CONTROLLER_PRIOR_TOP_K="${CONTROLLER_PRIOR_TOP_K:-1}"
CONTROLLER_PRIOR_SIMILARITY_THRESHOLD="${CONTROLLER_PRIOR_SIMILARITY_THRESHOLD:-0.0}"
CONTROLLER_INCLUDE_RAW_USER_CONTEXT="${CONTROLLER_INCLUDE_RAW_USER_CONTEXT:-0}"
CONTROLLER_RETRIEVAL_QUERY_AUGMENTATION="${CONTROLLER_RETRIEVAL_QUERY_AUGMENTATION:-0}"
CONTROLLER_DETERMINISTIC_NUMERIC_SUPERSEDE="${CONTROLLER_DETERMINISTIC_NUMERIC_SUPERSEDE:-0}"
ANSWER_RETRY_ON_UNKNOWN="${ANSWER_RETRY_ON_UNKNOWN:-0}"
CONTROLLER_TEMPORAL_SCAFFOLD="${CONTROLLER_TEMPORAL_SCAFFOLD:-0}"
CONTROLLER_COMPUTATION_ANSWERER="${CONTROLLER_COMPUTATION_ANSWERER:-0}"

RUNNER_ARGS=()
if [ "${CONTROLLER_INCLUDE_RAW_USER_CONTEXT}" = "1" ]; then
  RUNNER_ARGS+=(--controller-include-raw-user-context)
fi
if [ "${CONTROLLER_RETRIEVAL_QUERY_AUGMENTATION}" = "1" ]; then
  RUNNER_ARGS+=(--controller-retrieval-query-augmentation)
fi
if [ "${CONTROLLER_DETERMINISTIC_NUMERIC_SUPERSEDE}" = "1" ]; then
  RUNNER_ARGS+=(--controller-deterministic-numeric-supersede)
fi
if [ "${ANSWER_RETRY_ON_UNKNOWN}" = "1" ]; then
  RUNNER_ARGS+=(--answer-retry-on-unknown)
fi
if [ "${CONTROLLER_TEMPORAL_SCAFFOLD}" = "1" ]; then
  RUNNER_ARGS+=(--controller-temporal-scaffold)
fi
if [ "${CONTROLLER_COMPUTATION_ANSWERER}" = "1" ]; then
  RUNNER_ARGS+=(--controller-computation-answerer)
fi
if [ -n "${LIMIT}" ] && [ "${LIMIT}" != "none" ] && [ "${LIMIT}" != "full" ]; then
  RUNNER_ARGS+=(--limit "${LIMIT}")
fi

if [ -f venv/bin/activate ]; then
  source venv/bin/activate
elif [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

python scripts/run_m4w13_hf_a100_parallel.py \
  --slice "${SLICE}" \
  --out "${OUT}" \
  --systems "${SYSTEMS}" \
  --max-workers "${MAX_WORKERS}" \
  --status-s "${STATUS_S}" \
  --quality-preset "${QUALITY_PRESET}" \
  --hf-model "${HF_MODEL}" \
  --hf-max-seq-len "${HF_MAX_SEQ_LEN}" \
  --embedder-device "${EMBEDDER_DEVICE}" \
  --retrieval-k "${RETRIEVAL_K}" \
  --controller-memory-top-k "${CONTROLLER_MEMORY_TOP_K}" \
  --recency-memory-top-k "${RECENCY_MEMORY_TOP_K}" \
  --extraction-max-new-tokens "${EXTRACTION_MAX_NEW_TOKENS}" \
  --relation-max-new-tokens "${RELATION_MAX_NEW_TOKENS}" \
  --controller-retrieval-neighbor-window "${CONTROLLER_RETRIEVAL_NEIGHBOR_WINDOW}" \
  --controller-prior-top-k "${CONTROLLER_PRIOR_TOP_K}" \
  --controller-prior-similarity-threshold "${CONTROLLER_PRIOR_SIMILARITY_THRESHOLD}" \
  "${RUNNER_ARGS[@]}" \
  "$@"
