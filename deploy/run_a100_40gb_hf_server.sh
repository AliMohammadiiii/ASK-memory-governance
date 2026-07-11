#!/usr/bin/env bash
# One-shot setup + FINAL HuggingFace run on a fresh Ubuntu A100 40GB box.
#
# Unlike deploy/run_on_server.sh (which sets up the Ollama HTTP path), this
# script drives the IN-PROCESS HuggingFace path: each system subprocess loads
# its own Qwen2.5-7B fp16 copy on the GPU — no Ollama daemon, no model pulls
# from registry.ollama.ai (which is geo-blocked on some networks).
#
# It (1) gates on the GPU, (2) builds a Python>=3.11 venv with the [ml] stack
# (torch + transformers + sentence-transformers + faiss) plus ijson, (3)
# downloads the cleaned dataset and builds the full 500-question slice if it is
# not already present, then (4) hands off to run_a100_40gb_hf_final.sh.
#
# Run inside tmux/screen so it survives an SSH drop:
#
#   DATASET=m bash deploy/run_a100_40gb_hf_server.sh
#
#   DATASET     : m | s            (LongMemEval-M or -S; default m)
#   SYSTEMS     : b1,b2,b3,b4,controller | controller | ...   (default all five)
#   MAX_WORKERS : systems run at once. 2 is the safe A100-40GB ceiling for two
#                 7B fp16 copies (~30GB weights + KV + embedder). Raise ONLY
#                 after confirming free VRAM with nvidia-smi.
#   DATA_DIR    : where the cleaned release lives (default $HOME/longmemeval)
#   SLICE       : explicit slice path (skips download+build when set)
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
KIT_ROOT="$(cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
cd "${KIT_ROOT}"

DATASET="${DATASET:-m}"
SYSTEMS="${SYSTEMS:-b1,b2,b3,b4,controller}"
MAX_WORKERS="${MAX_WORKERS:-2}"
DATA_DIR="${DATA_DIR:-$HOME/longmemeval}"
DEFAULT_SLICE="data/slices/longmemeval_${DATASET}_full.jsonl"
SLICE="${SLICE:-${DEFAULT_SLICE}}"

echo "[hf-server] dataset=${DATASET} systems=${SYSTEMS} max_workers=${MAX_WORKERS}"

# 1) GPU gate. These 7B fp16 models are not viable on CPU, so stop early if the
#    driver is down rather than burning setup time then crawling.
if ! nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null; then
  echo "[hf-server] ERROR: nvidia-smi can't reach the NVIDIA driver."
  echo "  Diagnose:  lspci | grep -i nvidia"
  echo "  Driver mismatch after a kernel update is common:"
  echo "      sudo ubuntu-drivers autoinstall && sudo reboot"
  [ "${ALLOW_NO_GPU:-0}" = "1" ] || exit 1
fi

# 2) System packages (best effort; skipped without passwordless sudo, or when
#    SKIP_APT=1 — useful when `apt-get update` is slow behind the Ubuntu ESM
#    hook and python3-venv/build-essential are already installed).
if [ "${SKIP_APT:-0}" = "1" ]; then
  echo "[hf-server] SKIP_APT=1; skipping apt (assuming python3/venv/build tools present)"
elif command -v apt-get >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y python3-venv python3-pip build-essential || true
else
  echo "[hf-server] skipping apt (no passwordless sudo); assuming python3/venv present"
fi

# 3) Python >=3.11 venv (Ubuntu 22.04 ships 3.10; find/install a newer one).
PYBIN=""
for cand in python3.12 python3.11; do
  command -v "$cand" >/dev/null 2>&1 && { PYBIN="$cand"; break; }
done
if [ -z "${PYBIN}" ] && python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,11) else 1)' 2>/dev/null; then
  PYBIN=python3
fi
if [ -z "${PYBIN}" ]; then
  echo "[hf-server] Python >=3.11 not found (have $(python3 -V 2>&1)); installing 3.11 via deadsnakes"
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update -qq
  sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
  PYBIN=python3.11
fi
echo "[hf-server] using ${PYBIN} ($(${PYBIN} -V 2>&1))"
if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,11) else 1)' 2>/dev/null; then
  rm -rf .venv
  "${PYBIN}" -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip wheel "setuptools<82"

# 4) Project + ML stack. The [ml] extra pins torch/transformers/etc.; ijson
#    streams the large LongMemEval-M JSON array without loading it whole.
#    Skip the (slow) reinstall when torch is already importable unless forced.
if [ "${FORCE_REINSTALL:-0}" = "1" ] || ! python -c 'import torch, transformers, sentence_transformers' 2>/dev/null; then
  python -m pip install -e ".[ml]"
  python -m pip install ijson "huggingface_hub>=0.25" "hf_xet>=1.1"
else
  echo "[hf-server] ML stack already present; skipping reinstall (FORCE_REINSTALL=1 to override)"
fi
python - <<'PY'
import torch
print(f"[hf-server] torch={torch.__version__} cuda_available={torch.cuda.is_available()} "
      f"device={torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'}")
PY

# 5) Dataset + full slice (skip if the slice already exists).
if [ -f "${SLICE}" ]; then
  echo "[hf-server] slice present: ${SLICE} ($(wc -l < "${SLICE}") lines)"
else
  mkdir -p "${DATA_DIR}"
  SRC="${DATA_DIR}/longmemeval_${DATASET}_cleaned.json"
  if [ ! -f "${SRC}" ]; then
    echo "[hf-server] downloading LongMemEval-${DATASET^^} cleaned release"
    python deploy/download_longmemeval_s.py --dataset "${DATASET}" --out "${SRC}"
  fi
  echo "[hf-server] building full slice -> ${SLICE}"
  DATASET="${DATASET}" SRC="${SRC}" OUT="${SLICE}" bash deploy/build_full_slice.sh
fi

# 6) Final HF run (in-process, no Ollama). All strong controller knobs and the
#    max-a100-40gb quality preset are locked inside run_a100_40gb_hf_final.sh.
echo "[hf-server] launching final HF run"
SLICE="${SLICE}" SYSTEMS="${SYSTEMS}" MAX_WORKERS="${MAX_WORKERS}" \
  bash deploy/run_a100_40gb_hf_final.sh "$@"

echo "[hf-server] DONE. Reports: <OUT>/<system>/report.json"
echo "[hf-server] each report.json carries overall/answerable/abstention accuracy and n_degenerate_answers."
