#!/usr/bin/env bash
# OPTIONAL — pull the models a profile needs. Only useful when registry.ollama.ai
# is reachable (it is geo-blocked from some networks, incl. Iran — then this will
# TLS-timeout). Not called by run_eval.sh. Run manually if/when you have access
# (e.g. via a proxy: export HTTPS_PROXY=...).
#
#   PROFILE=t4 bash deploy/pull_models.sh
#
# If the registry is blocked, import a local GGUF instead:
#   printf 'FROM /path/to/model.gguf\n' > Modelfile
#   ollama create qwen3.5:9b -f Modelfile
set -euo pipefail

PROFILE="${PROFILE:-t4}"
case "${PROFILE}" in
  thesis) MODELS="llama3:8b phi3.5:3.8b llama3.2:3b" ;;
  light)  MODELS="llama3.2:3b phi3.5:3.8b" ;;
  *)      MODELS="qwen3.5:9b phi3.5:3.8b llama3.2:3b" ;;   # t4
esac

echo "[pull] profile=${PROFILE} models: ${MODELS}"
for m in ${MODELS}; do
  echo "[pull] ${m}"
  ollama pull "${m}"
done
echo "[pull] done."
