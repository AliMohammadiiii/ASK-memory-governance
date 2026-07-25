#!/usr/bin/env bash
# One-shot setup + FULL run on a fresh Ubuntu A100 box (non-Colab; uses $HOME,
# not /content). Installs deps, starts Ollama with parallelism, pulls the
# profile's models, downloads the cleaned dataset, builds the full 500-question
# slice, and runs all systems.
#
# Usage (run inside tmux/screen so it survives an SSH drop):
#   WORKERS=6 DATASET=s PROFILE=t4 bash deploy/run_on_server.sh
#
#   DATASET : s | m            (LongMemEval-S or -M)
#   PROFILE : t4 | thesis | light
#   WORKERS : parallel session shards (= OLLAMA_NUM_PARALLEL). 6 is a good
#             start on one A100 40GB; raise to 8 if VRAM/throughput allow.
#   SYSTEMS : all | b1,b2,b4,controller | ...
#   SKIP_OLLAMA_START=1 : use an already-running Ollama daemon instead of
#                         stopping/restarting it from this script.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
KIT_ROOT="$(cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
cd "${KIT_ROOT}"

DATASET="${DATASET:-s}"
PROFILE="${PROFILE:-t4}"
SYSTEMS="${SYSTEMS:-all}"
WORKERS="${WORKERS:-6}"
DATA_DIR="${DATA_DIR:-$HOME/longmemeval}"
export OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS:-2}"

case "${SKIP_OLLAMA_START:-0}" in
  1|true|TRUE|yes|YES|on|ON)
    SKIP_OLLAMA_START=1
    ;;
  0|false|FALSE|no|NO|off|OFF|"")
    SKIP_OLLAMA_START=0
    ;;
  *)
    echo "[server] ERROR: SKIP_OLLAMA_START must be 0/1, true/false, yes/no, or on/off; got '${SKIP_OLLAMA_START}'." >&2
    exit 2
    ;;
esac

echo "[server] dataset=${DATASET} profile=${PROFILE} workers=${WORKERS} skip_ollama_start=${SKIP_OLLAMA_START}"

# GPU gate: these models on CPU are not viable, so stop early if the driver is
# down rather than burning setup time and then crawling on CPU.
if nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null; then
  :
else
  echo "[server] ERROR: nvidia-smi can't reach the NVIDIA driver."
  echo "  Diagnose:  lspci | grep -i nvidia      # is an A100 actually attached?"
  echo "  If attached (driver mismatch after an apt/kernel update is common):"
  echo "      sudo ubuntu-drivers autoinstall && sudo reboot"
  echo "    then reconnect and confirm: nvidia-smi"
  echo "  If lspci shows NO NVIDIA device, this VM has no GPU — fix it in the"
  echo "  provider panel / contact support before running."
  echo "  (Override for a CPU smoke test only: ALLOW_NO_GPU=1)"
  [ "${ALLOW_NO_GPU:-0}" = "1" ] || exit 1
fi

# 1) System packages (best effort; skipped without passwordless sudo).
if command -v apt-get >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y python3-venv python3-pip unzip curl zstd build-essential || true
else
  echo "[server] skipping apt (no passwordless sudo); assuming python3/venv/curl present"
fi

# 2) Python env + deps. The package needs Python >=3.11; Ubuntu 22.04 ships
#    3.10, so find a 3.11/3.12 interpreter (install via deadsnakes if needed)
#    and (re)build the venv with it.
PYBIN=""
for cand in python3.12 python3.11; do
  command -v "$cand" >/dev/null 2>&1 && { PYBIN="$cand"; break; }
done
if [ -z "${PYBIN}" ] && python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,11) else 1)' 2>/dev/null; then
  PYBIN=python3
fi
if [ -z "${PYBIN}" ]; then
  echo "[server] Python >=3.11 not found (have $(python3 -V 2>&1)); installing 3.11 via deadsnakes"
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update -qq
  sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
  PYBIN=python3.11
fi
echo "[server] using ${PYBIN} ($(${PYBIN} -V 2>&1))"
# Recreate the venv if missing or built with the wrong (e.g. 3.10) interpreter.
if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,11) else 1)' 2>/dev/null; then
  rm -rf .venv
  "${PYBIN}" -m venv .venv
fi
source .venv/bin/activate
find .venv/lib/python*/site-packages -maxdepth 1 \
  \( -name '~sa-controller*' -o -name '~sa_controller*' \) \
  -exec rm -rf {} +
python -m pip install --upgrade pip wheel "setuptools<82"
python -m pip install -e .
python -m pip install -r deploy/colab_requirements.txt
python -m pip install ijson            # stream the large LongMemEval-M array

ollama_has_llama_server() {
  [ -x /usr/lib/ollama/llama-server ] || [ -x /usr/local/lib/ollama/llama-server ]
}

install_ollama_manual() {
  if ! sudo -n true 2>/dev/null; then
    echo "[server] ERROR: Ollama is missing or incomplete, and passwordless sudo is required to reinstall it."
    exit 1
  fi
  echo "[server] installing Ollama from official Linux tarball"
  sudo rm -rf /usr/lib/ollama /usr/local/lib/ollama
  sudo rm -f /usr/bin/ollama /usr/local/bin/ollama
  curl -fsSL https://ollama.com/download/ollama-linux-amd64.tar.zst | sudo tar --zstd -x -C /usr
  hash -r
}

# 3) Ollama: install if missing, then either use the already-running daemon or
#    (re)start WITH the parallelism env so the server actually serves concurrent
#    requests.
OLLAMA_PID=""
if [ "${SKIP_OLLAMA_START}" = "1" ]; then
  echo "[server] SKIP_OLLAMA_START=1; not installing or starting Ollama; using existing daemon"
else
  if ! command -v ollama >/dev/null 2>&1 || ! ollama_has_llama_server; then
    install_ollama_manual
  fi
  # The Ollama installer may leave a systemd service running with default env.
  # Stop it first; otherwise a manual `ollama serve` can silently lose the port
  # race and the long run will talk to the wrong daemon.
  if command -v systemctl >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    sudo systemctl stop ollama >/dev/null 2>&1 || true
  fi
  pkill -x ollama >/dev/null 2>&1 || true
  sleep 2
  nohup env OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_NUM_PARALLEL="${WORKERS}" \
    OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS}" \
    ollama serve > "$HOME/ollama.log" 2>&1 &
  OLLAMA_PID=$!
fi
OLLAMA_READY=0
for _ in $(seq 1 30); do
  curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
  sleep 2
done
if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  OLLAMA_READY=1
fi
if [ "${OLLAMA_READY}" != "1" ]; then
  echo "[server] ERROR: ollama did not become reachable. Last ~/ollama.log lines:"
  tail -80 "$HOME/ollama.log" || true
  exit 1
fi
if [ "${SKIP_OLLAMA_START}" = "1" ]; then
  echo "[server] ollama up: existing daemon reachable; parallelism is managed outside this script"
else
  echo "[server] ollama up: OLLAMA_NUM_PARALLEL=${WORKERS} OLLAMA_MAX_LOADED_MODELS=${OLLAMA_MAX_LOADED_MODELS}"
fi

# 4) Models: pull ONLY if explicitly requested. registry.ollama.ai is geo-blocked
#    on some networks (e.g. Iran → TLS-handshake timeout), so the default skips
#    pulling. Manage models yourself, or run deploy/pull_models.sh when you can.
if [ "${PULL_MODELS:-0}" = "1" ]; then
  PROFILE="${PROFILE}" bash deploy/pull_models.sh
else
  echo "[server] skipping model pull (PULL_MODELS=0); ensure models exist:"
  ollama list 2>/dev/null || true
fi
ANSWER_MODEL="$(printf '%s\n' ${MODELS} | head -n 1)"
PING_PAYLOAD="$(printf '{"model":"%s","messages":[{"role":"user","content":"reply with only: ok"}],"stream":false,"options":{"temperature":0,"num_predict":8,"num_ctx":2048}}' "${ANSWER_MODEL}")"
PING_STATUS="$(curl -sS -o /tmp/ask_ollama_ping.json -w '%{http_code}' http://127.0.0.1:11434/api/chat \
  -H 'Content-Type: application/json' \
  -d "${PING_PAYLOAD}" || true)"
if [ "${PING_STATUS}" != "200" ]; then
  echo "[server] ERROR: Ollama chat ping failed for ${ANSWER_MODEL} (HTTP ${PING_STATUS})."
  echo "[server] Response, if any:"
  cat /tmp/ask_ollama_ping.json 2>/dev/null || true
  echo
  echo "[server] Last ~/ollama.log lines:"
  tail -120 "$HOME/ollama.log" || true
  if [ -n "${OLLAMA_PID}" ]; then
    kill "${OLLAMA_PID}" >/dev/null 2>&1 || true
  fi
  exit 1
fi
echo "[server] ollama chat ping ok: ${ANSWER_MODEL}"

# 5) Download the cleaned dataset (S or M).
mkdir -p "${DATA_DIR}"
SRC="${DATA_DIR}/longmemeval_${DATASET}_cleaned.json"
if [ ! -f "${SRC}" ]; then
  python deploy/download_longmemeval_s.py --dataset "${DATASET}" --out "${SRC}"
fi

# 6) Build the full slice + run the suite. Ollama is already up, so
#    run_colab_lme_full.sh skips its own server start (no /content writes).
SRC="${SRC}" SESSION_WORKERS="${WORKERS}" \
  bash deploy/run_colab_lme_full.sh "${DATASET}" "${PROFILE}" "${SYSTEMS}"

echo "[server] DONE. Reports: runs/lme_${DATASET}_full_${PROFILE}_seed0/<system>/report.json"
echo "[server] each report.json carries answerable_accuracy / abstention_accuracy / n_degenerate_answers."
