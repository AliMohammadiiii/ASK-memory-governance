#!/usr/bin/env bash
# Complete Colab/GCE setup for Modal range runs.
#
# Run once after unzipping the project:
#   bash deploy/setup_colab_modal_range.sh
#
# Then run:
#   SAMPLE_FROM=50 SAMPLE_TO=100 SYSTEMS=controller SHARDS=4 \
#     bash deploy/run_colab_modal_range.sh
set -euo pipefail

cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

PYTHON="${PYTHON:-python3}"
DATASET="${DATASET:-m}"
SRC="${SRC:-data/longmemeval_${DATASET}_cleaned.json}"
SLICE="${SLICE:-data/slices/longmemeval_${DATASET}_full.jsonl}"
LOG_DIR="${LOG_DIR:-runs/setup_logs}"
SETUP_LOG="${SETUP_LOG:-${LOG_DIR}/setup_colab_modal_range.log}"

mkdir -p "${LOG_DIR}"
exec > >(tee -a "${SETUP_LOG}") 2>&1

echo "[setup-colab-modal] command:"
echo "  bash deploy/setup_colab_modal_range.sh"
echo "[setup-colab-modal] config:"
echo "  dataset=${DATASET}"
echo "  source=${SRC}"
echo "  slice=${SLICE}"
echo "  log=${SETUP_LOG}"
echo "  default_embed_model=jinaai/jina-embeddings-v5-text-nano"

echo "[setup-colab-modal] installing package + runtime dependencies"
"${PYTHON}" -m pip install -q -e .
"${PYTHON}" -m pip install -q \
  huggingface_hub \
  ijson \
  'faiss-cpu>=1.8,<2' \
  'sentence-transformers>=5.1.2' \
  'transformers>=4.56' \
  'accelerate>=1.0' \
  'peft>=0.15.2' \
  'torchao>=0.16.0' \
  einops \
  safetensors

if [[ ! -f "${SRC}" ]]; then
  echo "[setup-colab-modal] downloading LongMemEval-${DATASET^^} -> ${SRC}"
  "${PYTHON}" deploy/download_longmemeval_s.py --dataset "${DATASET}" --out "${SRC}"
else
  echo "[setup-colab-modal] source exists: ${SRC}"
fi

if [[ ! -f "${SLICE}" ]]; then
  echo "[setup-colab-modal] building full JSONL slice -> ${SLICE}"
  "${PYTHON}" scripts/build_slice.py --in "${SRC}" --out "${SLICE}" --n all
else
  echo "[setup-colab-modal] slice exists: ${SLICE}"
fi

echo "[setup-colab-modal] verifying imports"
"${PYTHON}" - <<'PY'
import faiss
import huggingface_hub
import ijson
import sentence_transformers
import torch

print("faiss ok")
print(f"huggingface_hub {huggingface_hub.__version__}")
print(f"ijson {ijson.__version__}")
print(f"sentence_transformers {sentence_transformers.__version__}")
print(f"torch {torch.__version__} cuda={torch.version.cuda} available={torch.cuda.is_available()}")
if not torch.cuda.is_available():
    raise SystemExit("CUDA is not available to torch; switch Colab to a GPU runtime.")
PY

echo "[setup-colab-modal] done"
