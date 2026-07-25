#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
KIT_ROOT="$(cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
cd "${KIT_ROOT}"

LOG_DIR="${ASK_LOG_DIR:-/content/ask_logs}"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/colab_prepare_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "${LOG_FILE}") 2>&1

log() {
  printf '[%s] [prepare] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

run() {
  log "RUN: $*"
  "$@"
  log "DONE: $*"
}

log "start colab_prepare.sh"
log "cwd=$(pwd)"
log "log_file=${LOG_FILE}"
log "python=$(command -v python || true)"
log "ASK_SETUP_OLLAMA=${ASK_SETUP_OLLAMA:-1}"
log "ASK_RUN_TESTS=${ASK_RUN_TESTS:-1}"

if python -m venv --system-site-packages .venv && [ -f .venv/bin/activate ] && [ -x .venv/bin/python ]; then
  # Colab sometimes disables ensurepip; use the venv when it works, but do
  # not depend on it. --system-site-packages keeps Colab's preinstalled torch
  # visible for the HuggingFace fast path.
  log "created .venv with --system-site-packages"
  source .venv/bin/activate
else
  log "WARN: venv creation failed; using the Colab Python environment directly."
  rm -rf .venv
fi

ACTIVE_PYTHON="$(command -v python)"
log "active_python=${ACTIVE_PYTHON}"
printf 'export ASK_PYTHON=%q\n' "${ACTIVE_PYTHON}" > .ask_colab_env
log "wrote .ask_colab_env with ASK_PYTHON=${ACTIVE_PYTHON}"
run python -m pip install --upgrade pip wheel "setuptools<82"
run python -m pip install -e .
run python -m pip install -r deploy/colab_requirements.txt

log "installing apt dependency: zstd"
run apt-get update -qq
run apt-get install -y zstd

if [ "${ASK_SETUP_OLLAMA:-1}" = "1" ]; then
  log "Ollama setup enabled"
  if ! command -v ollama >/dev/null 2>&1; then
    log "Ollama binary not found; installing"
    curl -fsSL https://ollama.com/install.sh | sh
  else
    log "Ollama binary already installed: $(command -v ollama)"
  fi

  log "restarting Ollama server"
  pkill -x ollama >/dev/null 2>&1 || true
  nohup env OLLAMA_HOST=127.0.0.1:11434 ollama serve > /content/ollama.log 2>&1 &
  log "waiting for Ollama health endpoint"
  for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  run curl -fsS http://127.0.0.1:11434/api/tags

  run ollama pull llama3.2:3b
  run ollama pull phi3.5:3.8b
  run ollama pull qwen3.5:9b
  run ollama pull phi4:14b
else
  log "Skipping Ollama setup because ASK_SETUP_OLLAMA=${ASK_SETUP_OLLAMA:-0}."
fi

log "downloading cleaned LongMemEval slice"
run python deploy/download_longmemeval_s.py \
  --out /content/longmemeval/longmemeval_s_cleaned.json

if [ "${ASK_RUN_TESTS:-1}" = "1" ]; then
  log "running package test suite"
  run python -m pytest tests -q
else
  log "skipping tests because ASK_RUN_TESTS=${ASK_RUN_TESTS:-0}"
fi

log "Colab setup complete."
log "Dataset: /content/longmemeval/longmemeval_s_cleaned.json"
log "Prepare log: ${LOG_FILE}"
