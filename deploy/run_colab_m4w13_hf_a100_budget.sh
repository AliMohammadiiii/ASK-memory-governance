#!/usr/bin/env bash
set -euo pipefail

# Budget A100 profile for quick decision runs. It avoids the two expensive
# ablation systems by default and lowers structured-output caps/top-k.

SYSTEMS="${SYSTEMS:-b1,b2,controller}"
OUT="${OUT:-runs/m4w13_a100_50_budget}"
MAX_WORKERS="${MAX_WORKERS:-2}"
CONTROLLER_MEMORY_TOP_K="${CONTROLLER_MEMORY_TOP_K:-12}"
RECENCY_MEMORY_TOP_K="${RECENCY_MEMORY_TOP_K:-12}"
EXTRACTION_MAX_NEW_TOKENS="${EXTRACTION_MAX_NEW_TOKENS:-128}"
RELATION_MAX_NEW_TOKENS="${RELATION_MAX_NEW_TOKENS:-64}"

export SYSTEMS
export OUT
export MAX_WORKERS
export CONTROLLER_MEMORY_TOP_K
export RECENCY_MEMORY_TOP_K
export EXTRACTION_MAX_NEW_TOKENS
export RELATION_MAX_NEW_TOKENS

bash deploy/run_colab_m4w13_hf_a100_parallel.sh "$@"
