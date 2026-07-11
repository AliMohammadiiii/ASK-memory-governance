#!/usr/bin/env bash
# Start (or confirm) the Ollama server WITH parallelism. No install, no pull.
# Run once per boot. Env: WORKERS (=OLLAMA_NUM_PARALLEL), OLLAMA_MAX_LOADED_MODELS.
#
#   WORKERS=4 bash deploy/serve.sh
set -euo pipefail

WORKERS="${WORKERS:-4}"
NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-${WORKERS}}"
MAX_LOADED="${OLLAMA_MAX_LOADED_MODELS:-2}"

if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "[serve] Ollama already running."
  echo "[serve] To change parallelism, stop it first:  pkill -x ollama  then re-run this."
else
  command -v ollama >/dev/null 2>&1 || { echo "[serve] ERROR: ollama not installed."; exit 1; }
  nohup env OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_NUM_PARALLEL="${NUM_PARALLEL}" \
    OLLAMA_MAX_LOADED_MODELS="${MAX_LOADED}" \
    ollama serve > "$HOME/ollama.log" 2>&1 &
  for _ in $(seq 1 30); do
    curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    sleep 2
  done
  echo "[serve] started: OLLAMA_NUM_PARALLEL=${NUM_PARALLEL} OLLAMA_MAX_LOADED_MODELS=${MAX_LOADED} (log: ~/ollama.log)"
fi

echo "[serve] installed models:"
ollama list 2>/dev/null || true
