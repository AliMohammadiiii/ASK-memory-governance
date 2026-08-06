#!/usr/bin/env bash
# Next-gen HF run on one A100 40GB: Qwen3.5-9B answerer (thinking OFF) +
# jina-embeddings-v5 retriever. This is an ABLATION path, intentionally kept
# separate from the verified Qwen2.5-7B / MiniLM run in
# run_a100_40gb_hf_final.sh:
#
#   * It builds an ISOLATED venv (.venv_nextgen) from the exact maintained lock
#     so the newer torch/transformers/peft never touch the pinned .venv.
#   * It does NOT use the max-a100-40gb quality preset (that preset hard-codes
#     Qwen2.5-7B + MiniLM). Every strong controller knob is passed explicitly.
#   * MAX_WORKERS defaults to 1: one 9B bf16 copy (~18GB) + the Jina embedder
#     (~3GB) + KV fits 40GB comfortably, but two 9B copies would OOM.
#   * --no-hf-enable-thinking suppresses Qwen3.5 <think> blocks (the harness
#     also strips any stray block) so the short-answer / JSON budget is spent
#     on the final answer.
#
# Run inside tmux/screen:
#   OFFLINE=1 DATASET=m bash deploy/run_a100_40gb_hf_nextgen.sh
#
#   OFFLINE=1   : models already in the HF cache; skip prefetch + run offline
#                 (set this on networks that can't reach huggingface.co).
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
KIT_ROOT="$(cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
cd "${KIT_ROOT}"

DATASET="${DATASET:-m}"
SYSTEMS="${SYSTEMS:-b1,b2,b3,b4,controller}"
MAX_WORKERS="${MAX_WORKERS:-1}"
HF_MODEL="${HF_MODEL:-Qwen/Qwen3.5-9B}"
HF_REVISION="${HF_REVISION:-}"
HF_DTYPE="${HF_DTYPE:-bfloat16}"
HF_MAX_SEQ_LEN="${HF_MAX_SEQ_LEN:-8192}"
EMBEDDER_MODEL="${EMBEDDER_MODEL:-jinaai/jina-embeddings-v5-text-small}"
EMBEDDER_REVISION="${EMBEDDER_REVISION:-}"
SLICE="${SLICE:-data/slices/longmemeval_${DATASET}_full.jsonl}"
OUT="${OUT:-runs/lme_${DATASET}_full_hf_nextgen_qwen35_9b_jina_seed0}"
VENV="${VENV:-.venv_nextgen}"

echo "[nextgen] model=${HF_MODEL} dtype=${HF_DTYPE} embedder=${EMBEDDER_MODEL}"
echo "[nextgen] systems=${SYSTEMS} max_workers=${MAX_WORKERS} slice=${SLICE}"

# 1) GPU gate.
if ! nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null; then
  echo "[nextgen] ERROR: nvidia-smi can't reach the NVIDIA driver." >&2
  [ "${ALLOW_NO_GPU:-0}" = "1" ] || exit 1
fi

# 2) Isolated CPython 3.12 environment with the exact maintained stack.
PYBIN="$(command -v python3.12 || true)"
if [ ! -x "${VENV}/bin/python" ] || ! "${VENV}/bin/python" -c 'import sys; sys.exit(0 if sys.version_info[:2]==(3,12) else 1)' 2>/dev/null; then
  [ -z "${PYBIN}" ] && { echo "[nextgen] ERROR: need CPython 3.12"; exit 1; }
  rm -rf "${VENV}"
  "${PYBIN}" -m venv "${VENV}"
fi
source "${VENV}/bin/activate"
python -m pip install --upgrade pip
if [ "${FORCE_REINSTALL:-0}" = "1" ] || ! python scripts/validation/validate_specialist_environment.py --profile ml >/dev/null 2>&1; then
  python -m pip install --require-hashes -r constraints/maintained-ml-py312.lock
  python -m pip install -e . --no-deps
else
  echo "[nextgen] next-gen stack already present (FORCE_REINSTALL=1 to override)"
fi
python -m pip check
python scripts/validation/validate_specialist_environment.py --profile ml
python - <<'PY'
import torch, transformers
print(f"[nextgen] torch={torch.__version__} transformers={transformers.__version__} "
      f"cuda={torch.cuda.is_available()}")
PY

# Make the runner subprocesses use THIS venv's interpreter.
export ASK_PYTHON="${KIT_ROOT}/${VENV}/bin/python"

# 3) Dataset + slice (skip when present).
if [ ! -f "${SLICE}" ]; then
  DATA_DIR="${DATA_DIR:-$HOME/longmemeval}"
  SRC="${DATA_DIR}/longmemeval_${DATASET}_cleaned.json"
  mkdir -p "${DATA_DIR}"
  [ -f "${SRC}" ] || python deploy/download_longmemeval_s.py --dataset "${DATASET}" --out "${SRC}"
  DATASET="${DATASET}" SRC="${SRC}" OUT="${SLICE}" bash deploy/build_full_slice.sh
fi

# 4) Offline switches + prefetch handling.
PREFETCH_ARGS=()
REVISION_ARGS=()
[ -n "${HF_REVISION}" ] && REVISION_ARGS+=(--hf-revision "${HF_REVISION}")
[ -n "${EMBEDDER_REVISION}" ] && REVISION_ARGS+=(--embedder-revision "${EMBEDDER_REVISION}")
if [ "${OFFLINE:-0}" = "1" ]; then
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  PREFETCH_ARGS+=(--no-prefetch)
  echo "[nextgen] OFFLINE=1: running from HF cache, prefetch disabled"
fi

# 5) Run. No quality preset; every strong controller knob is explicit. Thinking
#    OFF; Jina retriever with the retrieval task adapter.
python scripts/run_m4w13_hf_a100_parallel.py \
  --slice "${SLICE}" \
  --out "${OUT}" \
  --systems "${SYSTEMS}" \
  --max-workers "${MAX_WORKERS}" \
  --hf-model "${HF_MODEL}" \
  "${REVISION_ARGS[@]}" \
  --hf-dtype "${HF_DTYPE}" \
  --hf-max-seq-len "${HF_MAX_SEQ_LEN}" \
  --hf-trust-remote-code \
  --no-hf-enable-thinking \
  --retrieval-k 12 \
  --controller-memory-top-k 64 \
  --recency-memory-top-k 64 \
  --controller-retrieval-neighbor-window 2 \
  --controller-prior-top-k 3 \
  --controller-prior-similarity-threshold 0.45 \
  --controller-include-assistant-context \
  --controller-include-raw-user-context \
  --controller-retrieval-query-augmentation \
  --controller-deterministic-numeric-supersede \
  --answer-retry-on-unknown \
  --controller-temporal-scaffold \
  --controller-computation-answerer \
  --extraction-max-new-tokens 256 \
  --relation-max-new-tokens 128 \
  --embedder-backend sentence_transformer \
  --embedder-device cuda \
  --embedder-st-model "${EMBEDDER_MODEL}" \
  --embedder-trust-remote-code \
  --embedder-task retrieval \
  --clean-incomplete \
  "${PREFETCH_ARGS[@]}" \
  "$@"

echo "[nextgen] DONE. Reports: ${OUT}/<system>/report.json"
