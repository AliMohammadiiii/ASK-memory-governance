#!/usr/bin/env bash
# Start one vLLM OpenAI-compatible server for the role-based / cascade standard.
# Run TWO instances (different MODEL/PORT) for the 4B fast path and 9B
# escalation path, e.g. in two tmux windows:
#
#   # 4B fast path (extraction, primary relation, bulk/dev generation)
#   MODEL=./models/qwen35-4b NAME=qwen35-4b PORT=8000 \
#     MAX_NUM_SEQS=128 MAX_BATCHED_TOKENS=65536 GPU_FRAC=0.45 \
#     bash deploy/serve_vllm.sh
#
#   # 9B escalation path (relation escalation, final / judge-sensitive)
#   MODEL=./models/qwen35-9b NAME=qwen35-9b PORT=8001 \
#     MAX_NUM_SEQS=64 MAX_BATCHED_TOKENS=32768 GPU_FRAC=0.50 \
#     bash deploy/serve_vllm.sh
#
# Two servers share one A100 40GB: keep the GPU_FRAC values so the sum leaves
# headroom (0.45 + 0.50 here). For the fairest benchmark, run them in separate
# phases instead (one server at a time at GPU_FRAC=0.90). 9B BF16 weights are
# ~19GB; 4B ~8GB — both fit with KV cache for 8K context.
set -euo pipefail

MODEL="${MODEL:?set MODEL to a local model dir or HF id}"
NAME="${NAME:?set NAME (served-model-name), e.g. qwen35-9b}"
PORT="${PORT:-8000}"
DTYPE="${DTYPE:-bfloat16}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
GPU_FRAC="${GPU_FRAC:-0.90}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}"
MAX_BATCHED_TOKENS="${MAX_BATCHED_TOKENS:-32768}"
HOST="${HOST:-0.0.0.0}"
# Qwen3.5 is a hybrid (Mamba) model. Prefix caching over Mamba layers is
# experimental in vLLM and can fail engine init; set PREFIX_CACHING=0 to disable.
# ENFORCE_EAGER=1 skips CUDA-graph capture (slower, but rules out a capture bug).
PREFIX_CACHING="${PREFIX_CACHING:-1}"
ENFORCE_EAGER="${ENFORCE_EAGER:-0}"
EXTRA_ARGS="${EXTRA_ARGS:-}"

# Non-thinking by default (Qwen3.5): suppress <think> blocks server-side so the
# short answer/JSON budget is spent on the final answer.
THINKING_KW="${THINKING_KW:-{\"enable_thinking\": false}}"

# FlashInfer JIT-compiles its sampling kernel with nvcc at startup. This box has
# the driver but no CUDA toolkit (no nvcc), so the build fails. The eval is
# greedy (temperature=0), so the native sampler is sufficient — disable the
# FlashInfer sampler (and autotune) to skip the JIT entirely. Override only if
# you install the CUDA toolkit.
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"
export VLLM_USE_FLASHINFER_MOE_FP16="${VLLM_USE_FLASHINFER_MOE_FP16:-0}"

echo "[vllm] serve name=${NAME} model=${MODEL} port=${PORT} dtype=${DTYPE} "
echo "[vllm]   max_model_len=${MAX_MODEL_LEN} max_num_seqs=${MAX_NUM_SEQS} gpu_frac=${GPU_FRAC}"

ARGS=(
  --served-model-name "${NAME}"
  --dtype "${DTYPE}"
  --max-model-len "${MAX_MODEL_LEN}"
  --gpu-memory-utilization "${GPU_FRAC}"
  --max-num-seqs "${MAX_NUM_SEQS}"
  --max-num-batched-tokens "${MAX_BATCHED_TOKENS}"
  --default-chat-template-kwargs "${THINKING_KW}"
  --host "${HOST}"
  --port "${PORT}"
)
[ "${PREFIX_CACHING}" = "1" ] && ARGS+=(--enable-prefix-caching) || ARGS+=(--no-enable-prefix-caching)
[ "${ENFORCE_EAGER}" = "1" ] && ARGS+=(--enforce-eager)
# shellcheck disable=SC2206
[ -n "${EXTRA_ARGS}" ] && ARGS+=(${EXTRA_ARGS})

exec vllm serve "${MODEL}" "${ARGS[@]}"
