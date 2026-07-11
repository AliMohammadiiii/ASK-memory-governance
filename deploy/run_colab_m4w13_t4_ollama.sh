#!/usr/bin/env bash
set -euo pipefail

# One-command Colab/T4 runner for the LongMemEval-S 50 controller run on local
# Ollama models, with the 2026-06-08 accuracy + latency fixes enabled.
#
# Defaults (QUALITY=t4) turn on the validated accuracy knobs at T4-affordable
# levels: assistant context, answer-retry, semantic prior-top-k=3 with a 0.45
# similarity gate (the latency lever), retrieval k=10, +/-1 neighbor window,
# temporal scaffolding, and deterministic computation-answer bypasses.
# Extraction stays bounded at 32 turns/question.
#
#   PROFILE=t4      -> qwen3.5:9b answerer, llama3.2:3b extractor, phi3.5 judge/classifier
#   QUALITY=t4      -> the accuracy bundle above (set QUALITY=none for the old baseline)
#
# The run is resumable: re-running after a Colab disconnect skips finished
# sessions and reuses the extraction/relation/answer caches in OUT.
#
# Override examples:
#   SYSTEMS=controller bash deploy/run_colab_m4w13_t4_ollama.sh
#   QUALITY=none SYSTEMS=controller bash deploy/run_colab_m4w13_t4_ollama.sh
#   LIMIT=10 bash deploy/run_colab_m4w13_t4_ollama.sh   # quick smoke

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
KIT_ROOT="$(cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
cd "${KIT_ROOT}"

PROFILE="${PROFILE:-t4}"          # t4 | light
QUALITY="${QUALITY:-t4}"          # t4 | none
SYSTEMS="${SYSTEMS:-controller}"  # controller | all | comma list
SLICE="${SLICE:-data/slices/longmemeval_s_cleaned_50_seed0.jsonl}"
OUT="${OUT:-runs/m4w13_50_t4_quality}"
SEED="${SEED:-0}"
N_BOOTSTRAP="${N_BOOTSTRAP:-1000}"
LIMIT="${LIMIT:-}"                # empty = full slice
OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
OLLAMA_TIMEOUT_S="${OLLAMA_TIMEOUT_S:-1800}"
# Throughput knobs. The pipeline interleaves extraction (llama) -> relation
# (phi) -> answer (qwen) many times per question, so MAX_LOADED_MODELS must be
# >= the number of role models or Ollama thrashes by unload/reloading the model
# on every call (the dominant latency on the first run). NUM_PARALLEL and
# SESSION_WORKERS fill the otherwise-idle GPU with concurrent questions.
#
# Defaults target a 24 GB GPU (A10 / L4): the 3 role models total ~12 GB, so
# 3 resident models + 3 parallel slots + 3 session workers fit comfortably.
# On a 16 GB T4, lower to SESSION_WORKERS=2 OLLAMA_NUM_PARALLEL=2.
SESSION_WORKERS="${SESSION_WORKERS:-3}"
OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-3}"
OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS:-3}"
JUDGE_TIMEOUT_S="${JUDGE_TIMEOUT_S:-1800}"
EMBEDDER_BACKEND="${EMBEDDER_BACKEND:-sentence_transformer}"
# Embed MiniLM on the GPU so the retrieval/prefilter embedding work does not
# compete with the worker processes for the 2 CPU cores. Falls back to CPU
# automatically if the torch build has no CUDA.
EMBEDDER_DEVICE="${EMBEDDER_DEVICE:-cuda}"
KSA_INSTALL_DEPS="${KSA_INSTALL_DEPS:-1}"
KSA_SETUP_OLLAMA="${KSA_SETUP_OLLAMA:-1}"
KSA_PULL_MODELS="${KSA_PULL_MODELS:-1}"
KSA_RUN_TESTS="${KSA_RUN_TESTS:-smoke}" # 0 | smoke | full
KSA_RUN_PREFLIGHT="${KSA_RUN_PREFLIGHT:-1}"
RESULT_ZIP="${RESULT_ZIP:-/content/ksa_m4w13_50_${QUALITY}_results_$(date +%Y%m%d_%H%M%S).zip}"
LOG_DIR="${KSA_LOG_DIR:-/content/ksa_logs}"

case "${PROFILE}" in
  t4)
    REQUIRED_MODELS=("qwen3.5:9b" "llama3.2:3b" "phi3.5:3.8b")
    ;;
  light)
    REQUIRED_MODELS=("llama3.2:3b" "phi3.5:3.8b")
    ;;
  *)
    echo "PROFILE must be 't4' or 'light'; got ${PROFILE}" >&2
    exit 2
    ;;
esac

mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/m4w13_${QUALITY}_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "${LOG_FILE}") 2>&1

log() {
  printf '[%s] [m4w13-t4] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

run() {
  log "RUN: $*"
  "$@"
  log "DONE: $*"
}

activate_or_create_venv() {
  if [ -f .venv/bin/activate ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
    return
  fi
  if [ -f venv/bin/activate ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
    return
  fi
  if [ "${KSA_INSTALL_DEPS}" != "1" ]; then
    log "No venv found and KSA_INSTALL_DEPS=${KSA_INSTALL_DEPS}; using active Python."
    return
  fi
  log "Creating .venv with --system-site-packages"
  if python -m venv --system-site-packages .venv; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
    log "Using newly created .venv"
  else
    log "WARN: venv creation failed (Colab ensurepip unavailable). Using active Python."
    rm -rf .venv
  fi
}

install_deps() {
  if [ "${KSA_INSTALL_DEPS}" != "1" ]; then
    log "Skipping dependency install."
    return
  fi
  run python -m pip install --upgrade pip wheel "setuptools<82"
  # sentence-transformers is needed for the MiniLM retrieval embedder.
  run python -m pip install -e '.[dev,ml]'
}

ensure_ollama() {
  if [ "${KSA_SETUP_OLLAMA}" != "1" ]; then
    log "Skipping Ollama setup."
    return
  fi
  if ! command -v ollama >/dev/null 2>&1; then
    log "Ollama binary not found; installing."
    curl -fsSL https://ollama.com/install.sh | sh
  fi

  # Always (re)start Ollama with our throughput env so the loaded-models /
  # parallelism settings actually take effect (a server already running with
  # the wrong env would otherwise keep thrashing).
  log "Starting Ollama: NUM_PARALLEL=${OLLAMA_NUM_PARALLEL} MAX_LOADED_MODELS=${OLLAMA_MAX_LOADED_MODELS}"
  pkill -x ollama >/dev/null 2>&1 || true
  sleep 1
  nohup env \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL}" \
    OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS}" \
    ollama serve > /content/ollama.log 2>&1 &
  for _ in $(seq 1 45); do
    if curl -fsS "${OLLAMA_HOST%/}/api/tags" >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  run curl -fsS "${OLLAMA_HOST%/}/api/tags"

  if [ "${KSA_PULL_MODELS}" = "1" ]; then
    for model in "${REQUIRED_MODELS[@]}"; do
      run ollama pull "${model}"
    done
  else
    log "Skipping model pulls."
  fi
}

run_tests() {
  case "${KSA_RUN_TESTS}" in
    0|false|False|none)
      log "Skipping tests."
      ;;
    smoke)
      run python -m pytest -q \
        tests/test_pipeline_orchestrator.py \
        tests/test_computation_replay.py \
        tests/test_failed_slice_builder.py \
        tests/test_controller.py \
        tests/test_supersede.py \
        tests/test_m4w13_ollama_runner.py
      ;;
    full)
      run python -m pytest tests -q
      ;;
    *)
      echo "KSA_RUN_TESTS must be 0, smoke, or full; got ${KSA_RUN_TESTS}" >&2
      exit 2
      ;;
  esac
}

run_preflight() {
  if [ "${KSA_RUN_PREFLIGHT}" != "1" ]; then
    log "Skipping computation preflight."
    return
  fi
  local smoke_slice="data/slices/longmemeval_s_cleaned_50_seed0.jsonl"
  if [ ! -f "${smoke_slice}" ]; then
    log "Skipping computation preflight; missing ${smoke_slice}."
    return
  fi
  run python scripts/simulate_computation_answerer.py \
    --slice "${smoke_slice}" \
    --mode supporting \
    --session-id f0853d11 \
    --json
  run python scripts/simulate_computation_answerer.py \
    --slice "${smoke_slice}" \
    --mode haystack \
    --session-id gpt4_70e84552_abs \
    --json
}

zip_results() {
  run zip -r "${RESULT_ZIP}" \
    "${OUT}" \
    FIXES_2026-06-08.md \
    configs/controller_active.yaml \
    prompts/extraction_v_final2.j2 \
    prompts/relation_stage1_v0.j2 \
    prompts/relation_stage2_v0.j2 \
    deploy/COLAB_M4W13_T4_RUNBOOK.md
  log "RESULT_ZIP=${RESULT_ZIP}"
}

log "start"
log "cwd=$(pwd)"
log "profile=${PROFILE} quality=${QUALITY} systems=${SYSTEMS}"
log "slice=${SLICE} out=${OUT} limit=${LIMIT:-<full>}"
log "log_file=${LOG_FILE}"
log "KSA_RUN_TESTS=${KSA_RUN_TESTS} KSA_RUN_PREFLIGHT=${KSA_RUN_PREFLIGHT}"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi || true
fi

activate_or_create_venv
log "python=$(command -v python)"
install_deps
ensure_ollama
run_tests
run_preflight

RUNNER_ARGS=(
  --model-profile "${PROFILE}"
  --quality "${QUALITY}"
  --systems "${SYSTEMS}"
  --slice "${SLICE}"
  --out "${OUT}"
  --seed "${SEED}"
  --n-bootstrap "${N_BOOTSTRAP}"
  --ollama-host "${OLLAMA_HOST}"
  --ollama-timeout-s "${OLLAMA_TIMEOUT_S}"
  --judge-timeout-s "${JUDGE_TIMEOUT_S}"
  --embedder-backend "${EMBEDDER_BACKEND}"
  --embedder-device "${EMBEDDER_DEVICE}"
  --session-workers "${SESSION_WORKERS}"
  --resume
)
if [ -n "${LIMIT}" ]; then
  RUNNER_ARGS+=(--limit "${LIMIT}")
fi

run python scripts/run_m4w13_ollama.py "${RUNNER_ARGS[@]}" "$@"

zip_results
log "done"
