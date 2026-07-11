#!/usr/bin/env bash
set -euo pipefail

# A10G first-pass profile: run only the controller by default. This keeps one
# HF process on a smaller GPU and avoids paying for b3/b4 ablations.

SYSTEMS="${SYSTEMS:-controller}"
OUT="${OUT:-runs/m4w13_a10g_controller_50}"
MAX_WORKERS="${MAX_WORKERS:-1}"
CONTROLLER_MEMORY_TOP_K="${CONTROLLER_MEMORY_TOP_K:-8}"
RECENCY_MEMORY_TOP_K="${RECENCY_MEMORY_TOP_K:-8}"
EXTRACTION_MAX_NEW_TOKENS="${EXTRACTION_MAX_NEW_TOKENS:-128}"
RELATION_MAX_NEW_TOKENS="${RELATION_MAX_NEW_TOKENS:-64}"
CONTROLLER_RETRIEVAL_NEIGHBOR_WINDOW="${CONTROLLER_RETRIEVAL_NEIGHBOR_WINDOW:-2}"

export SYSTEMS
export OUT
export MAX_WORKERS
export CONTROLLER_MEMORY_TOP_K
export RECENCY_MEMORY_TOP_K
export EXTRACTION_MAX_NEW_TOKENS
export RELATION_MAX_NEW_TOKENS
export CONTROLLER_RETRIEVAL_NEIGHBOR_WINDOW

bash deploy/run_colab_m4w13_hf_a100_parallel.sh --no-require-a100 "$@"
