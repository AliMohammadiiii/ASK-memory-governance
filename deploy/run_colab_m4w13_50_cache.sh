#!/usr/bin/env bash
set -euo pipefail

# One-command LongMemEval-S 50 run for controller + baselines.
#
# Default profile ("balanced") is the best cost/time tradeoff for getting the
# complete 50-session artifact bundle: one HF process per system on an A100,
# resumable output directories, strict validation, and a final zip.
#
# Override examples:
#   SYSTEMS=controller bash deploy/run_colab_m4w13_50_cache.sh
#   PROFILE=quality SYSTEMS=all bash deploy/run_colab_m4w13_50_cache.sh
#   REQUIRE_A100=0 PROFILE=quality SYSTEMS=controller bash deploy/run_colab_m4w13_50_cache.sh

SLICE="${SLICE:-data/slices/longmemeval_s_cleaned_50_seed0.jsonl}"
PROFILE="${PROFILE:-balanced}" # balanced | quality
SYSTEMS="${SYSTEMS:-all}"
LIMIT="${LIMIT:-50}"
SEED="${SEED:-0}"
N_BOOTSTRAP="${N_BOOTSTRAP:-1000}"
OUT="${OUT:-runs/m4w13_50_${PROFILE}}"
STATUS_S="${STATUS_S:-30}"
EMBEDDER_DEVICE="${EMBEDDER_DEVICE:-auto}"
ZIP_OUT="${ZIP_OUT:-}"
REQUIRE_A100="${REQUIRE_A100:-1}"
CLEAN_INCOMPLETE="${CLEAN_INCOMPLETE:-0}"
NO_PREFETCH="${NO_PREFETCH:-0}"
export PYTHONHASHSEED="${PYTHONHASHSEED:-0}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"

case "${PROFILE}" in
  balanced)
    HF_MODEL="${HF_MODEL:-Qwen/Qwen2.5-3B-Instruct}"
    MAX_WORKERS="${MAX_WORKERS:-5}"
    RETRIEVAL_K="${RETRIEVAL_K:-5}"
    CONTROLLER_MEMORY_TOP_K="${CONTROLLER_MEMORY_TOP_K:-32}"
    RECENCY_MEMORY_TOP_K="${RECENCY_MEMORY_TOP_K:-32}"
    EXTRACTION_MAX_NEW_TOKENS="${EXTRACTION_MAX_NEW_TOKENS:-192}"
    RELATION_MAX_NEW_TOKENS="${RELATION_MAX_NEW_TOKENS:-96}"
    CONTROLLER_RETRIEVAL_NEIGHBOR_WINDOW="${CONTROLLER_RETRIEVAL_NEIGHBOR_WINDOW:-0}"
    ;;
  quality)
    HF_MODEL="${HF_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
    MAX_WORKERS="${MAX_WORKERS:-1}"
    RETRIEVAL_K="${RETRIEVAL_K:-12}"
    CONTROLLER_MEMORY_TOP_K="${CONTROLLER_MEMORY_TOP_K:-64}"
    RECENCY_MEMORY_TOP_K="${RECENCY_MEMORY_TOP_K:-32}"
    EXTRACTION_MAX_NEW_TOKENS="${EXTRACTION_MAX_NEW_TOKENS:-256}"
    RELATION_MAX_NEW_TOKENS="${RELATION_MAX_NEW_TOKENS:-128}"
    CONTROLLER_RETRIEVAL_NEIGHBOR_WINDOW="${CONTROLLER_RETRIEVAL_NEIGHBOR_WINDOW:-2}"
    ;;
  *)
    echo "unknown PROFILE=${PROFILE}; expected balanced or quality" >&2
    exit 2
    ;;
esac

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  export KSA_PYTHON="$(command -v python)"
elif [ -f venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
  export KSA_PYTHON="$(command -v python)"
elif [ -f .ksa_colab_env ]; then
  # shellcheck disable=SC1091
  source .ksa_colab_env
elif [ -n "${KSA_PYTHON:-}" ] && [ ! -x "${KSA_PYTHON}" ]; then
  echo "[m4w13-50] ignoring non-executable KSA_PYTHON=${KSA_PYTHON}"
  unset KSA_PYTHON
fi

if [ -z "${KSA_PYTHON:-}" ]; then
  DEFAULT_PYTHON="$(command -v python || command -v python3 || true)"
  if [ -z "${DEFAULT_PYTHON}" ]; then
    echo "[m4w13-50] could not find python or python3" >&2
    exit 2
  fi
  export KSA_PYTHON="${DEFAULT_PYTHON}"
fi

EXTRA_ARGS=()
if [ "${REQUIRE_A100}" = "0" ]; then
  EXTRA_ARGS+=(--no-require-a100)
fi
if [ "${CLEAN_INCOMPLETE}" = "1" ]; then
  EXTRA_ARGS+=(--clean-incomplete)
fi
if [ "${NO_PREFETCH}" = "1" ]; then
  EXTRA_ARGS+=(--no-prefetch)
fi
if [ -n "${ZIP_OUT}" ]; then
  EXTRA_ARGS+=(--zip-out "${ZIP_OUT}")
fi

echo "[m4w13-50] profile=${PROFILE} systems=${SYSTEMS} out=${OUT}"
echo "[m4w13-50] slice=${SLICE} limit=${LIMIT} max_workers=${MAX_WORKERS} hf_model=${HF_MODEL}"
echo "[m4w13-50] seed=${SEED} n_bootstrap=${N_BOOTSTRAP} pythonhashseed=${PYTHONHASHSEED}"

RUNNER_ARGS=(
  --slice "${SLICE}"
  --out "${OUT}"
  --systems "${SYSTEMS}"
  --limit "${LIMIT}"
  --seed "${SEED}"
  --n-bootstrap "${N_BOOTSTRAP}"
  --max-workers "${MAX_WORKERS}"
  --status-s "${STATUS_S}"
  --hf-model "${HF_MODEL}"
  --embedder-device "${EMBEDDER_DEVICE}"
  --retrieval-k "${RETRIEVAL_K}"
  --controller-memory-top-k "${CONTROLLER_MEMORY_TOP_K}"
  --recency-memory-top-k "${RECENCY_MEMORY_TOP_K}"
  --extraction-max-new-tokens "${EXTRACTION_MAX_NEW_TOKENS}"
  --relation-max-new-tokens "${RELATION_MAX_NEW_TOKENS}"
  --controller-retrieval-neighbor-window "${CONTROLLER_RETRIEVAL_NEIGHBOR_WINDOW}"
)

if [ "${PROFILE}" = "quality" ]; then
  RUNNER_ARGS+=(--quality-preset max-a10g)
fi
if [ "${#EXTRA_ARGS[@]}" -gt 0 ]; then
  RUNNER_ARGS+=("${EXTRA_ARGS[@]}")
fi

"${KSA_PYTHON}" scripts/run_m4w13_hf_a100_parallel.py "${RUNNER_ARGS[@]}" "$@"
