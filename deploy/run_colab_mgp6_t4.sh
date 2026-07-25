#!/usr/bin/env bash
set -euo pipefail

# One-command Colab/T4 runner for the repaired MGP-6 -> metrics -> RC@C path.
#
# Defaults are T4-practical development artifacts:
#   PROFILE=t4    -> llama3.2:3b extractor, phi3.5:3.8b classifier
#
# Citable final-candidate artifacts require:
#   PROFILE=thesis -> llama3:8b extractor/classifier; eligible for promotion gate

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
KIT_ROOT="$(cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
cd "${KIT_ROOT}"

PROFILE="${PROFILE:-t4}" # t4 | thesis
MGP6="${MGP6:-data/mgp6_v1_seed0.jsonl}"
OUT="${OUT:-runs/m4w14_${PROFILE}}"
RC_OUT="${RC_OUT:-runs/m4w15_${PROFILE}}"
SEED="${SEED:-0}"
N_BOOTSTRAP="${N_BOOTSTRAP:-1000}"
OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
OLLAMA_TIMEOUT_S="${OLLAMA_TIMEOUT_S:-1800}"
STRUCTURED_NUM_CTX="${STRUCTURED_NUM_CTX:-4096}"
EXTRACTION_MAX_NEW_TOKENS="${EXTRACTION_MAX_NEW_TOKENS:-512}"
RELATION_MAX_NEW_TOKENS="${RELATION_MAX_NEW_TOKENS:-128}"
ASK_INSTALL_DEPS="${ASK_INSTALL_DEPS:-1}"
ASK_SETUP_OLLAMA="${ASK_SETUP_OLLAMA:-1}"
ASK_PULL_MODELS="${ASK_PULL_MODELS:-1}"
ASK_RUN_TESTS="${ASK_RUN_TESTS:-smoke}" # 0 | smoke | full
FAIL_ON_SANITY="${FAIL_ON_SANITY:-1}"
REQUIRE_PROMOTION="${REQUIRE_PROMOTION:-0}"
RESULT_ZIP="${RESULT_ZIP:-/content/ask_mgp6_${PROFILE}_results_$(date +%Y%m%d_%H%M%S).zip}"
LOG_DIR="${ASK_LOG_DIR:-/content/ask_logs}"

case "${PROFILE}" in
  t4|light)
    RUN_PROFILE="t4"
    REQUIRED_MODELS=("llama3.2:3b" "phi3.5:3.8b")
    ;;
  thesis)
    RUN_PROFILE="thesis"
    REQUIRED_MODELS=("llama3:8b" "phi3.5:3.8b")
    ;;
  *)
    echo "PROFILE must be 't4' or 'thesis'; got ${PROFILE}" >&2
    exit 2
    ;;
esac

mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/mgp6_${PROFILE}_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "${LOG_FILE}") 2>&1

log() {
  printf '[%s] [mgp6-t4] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
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
  if [ "${ASK_INSTALL_DEPS}" != "1" ]; then
    log "No venv found and ASK_INSTALL_DEPS=${ASK_INSTALL_DEPS}; using active Python."
    return
  fi
  log "Creating .venv with --system-site-packages"
  if python -m venv --system-site-packages .venv; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
    log "Using newly created .venv"
  else
    log "WARN: venv creation failed, usually because Colab ensurepip is unavailable."
    log "WARN: Continuing with the active Colab Python environment."
    rm -rf .venv
  fi
}

install_deps() {
  if [ "${ASK_INSTALL_DEPS}" != "1" ]; then
    log "Skipping dependency install."
    return
  fi
  run python -m pip install --upgrade pip wheel "setuptools<82"
  run python -m pip install -e '.[dev]'
}

ensure_ollama() {
  if [ "${ASK_SETUP_OLLAMA}" != "1" ]; then
    log "Skipping Ollama setup."
    return
  fi
  if ! command -v ollama >/dev/null 2>&1; then
    log "Ollama binary not found; installing."
    curl -fsSL https://ollama.com/install.sh | sh
  fi

  if ! curl -fsS "${OLLAMA_HOST%/}/api/tags" >/dev/null 2>&1; then
    log "Starting Ollama with one loaded model / one parallel request for T4 stability."
    pkill -x ollama >/dev/null 2>&1 || true
    nohup env \
      OLLAMA_HOST=127.0.0.1:11434 \
      OLLAMA_NUM_PARALLEL=1 \
      OLLAMA_MAX_LOADED_MODELS=1 \
      ollama serve > /content/ollama.log 2>&1 &
    for _ in $(seq 1 45); do
      if curl -fsS "${OLLAMA_HOST%/}/api/tags" >/dev/null 2>&1; then
        break
      fi
      sleep 2
    done
  fi
  run curl -fsS "${OLLAMA_HOST%/}/api/tags"

  if [ "${ASK_PULL_MODELS}" = "1" ]; then
    for model in "${REQUIRED_MODELS[@]}"; do
      run ollama pull "${model}"
    done
  else
    log "Skipping model pulls."
  fi
}

run_tests() {
  case "${ASK_RUN_TESTS}" in
    0|false|False|none)
      log "Skipping tests."
      ;;
    smoke)
      run python -m pytest -q \
        tests/test_extraction_repair_regression.py \
        tests/test_classifier_schema_normalization.py \
        tests/test_thesis_profile_tier_guard.py \
        tests/test_recoverability.py \
        tests/test_smrr.py \
        tests/test_m4w15.py
      ;;
    full)
      run python -m pytest tests -q
      ;;
    *)
      echo "ASK_RUN_TESTS must be 0, smoke, or full; got ${ASK_RUN_TESTS}" >&2
      exit 2
      ;;
  esac
}

zip_results() {
  local promotion_log="${OUT}/promotion_gate.txt"
  run zip -r "${RESULT_ZIP}" \
    "${OUT}" \
    "${RC_OUT}" \
    "${promotion_log}" \
    NOTES/m4w14_mgp6_results.md \
    ARTIFACT_MANIFEST.md \
    configs/controller_active.yaml \
    configs/eval_mgp6_final.yaml \
    prompts/extraction_v_final2.j2 \
    prompts/relation_stage1_v0.j2 \
    prompts/relation_stage2_v0.j2 \
    deploy/COLAB_MGP6_T4_RUNBOOK.md
  log "RESULT_ZIP=${RESULT_ZIP}"
}

log "start"
log "cwd=$(pwd)"
log "profile=${PROFILE} run_profile=${RUN_PROFILE}"
log "out=${OUT} rc_out=${RC_OUT}"
log "log_file=${LOG_FILE}"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi || true
fi

activate_or_create_venv
log "python=$(command -v python)"
install_deps
ensure_ollama
run_tests

SANITY_ARGS=()
if [ "${FAIL_ON_SANITY}" = "1" ]; then
  SANITY_ARGS+=(--fail-on-sanity)
fi

run python scripts/run_mgp6.py \
  --input "${MGP6}" \
  --systems all \
  --model-profile "${RUN_PROFILE}" \
  --seed "${SEED}" \
  --n-bootstrap "${N_BOOTSTRAP}" \
  --scorecard-config configs/controller_active.yaml \
  --out "${OUT}" \
  --note-path NOTES/m4w14_mgp6_results.md \
  --ollama-host "${OLLAMA_HOST}" \
  --ollama-timeout-s "${OLLAMA_TIMEOUT_S}" \
  --structured-num-ctx "${STRUCTURED_NUM_CTX}" \
  --extraction-max-new-tokens "${EXTRACTION_MAX_NEW_TOKENS}" \
  --relation-max-new-tokens "${RELATION_MAX_NEW_TOKENS}" \
  "${SANITY_ARGS[@]}"

run python scripts/evaluate_recoverability_mgp6.py \
  --mgp6 "${MGP6}" \
  --run-root "${OUT}"

run python scripts/evaluate_smrr_mgp6.py \
  --mgp6 "${MGP6}" \
  --run-root "${OUT}" \
  --out "${OUT}/smrr_report.json" \
  --csv "${OUT}/smrr_table.csv"

run python scripts/evaluate_rc_at_c_mgp6.py \
  --mgp6 "${MGP6}" \
  --run-root "${OUT}" \
  --out "${RC_OUT}" \
  --n-bootstrap "${N_BOOTSTRAP}" \
  --seed "${SEED}"

mkdir -p "${OUT}"
set +e
python scripts/promote_to_final.py \
  --run-root "${OUT}" \
  --mgp6 "${MGP6}" \
  --check-only | tee "${OUT}/promotion_gate.txt"
PROMOTION_STATUS="${PIPESTATUS[0]}"
set -e
log "promotion_status=${PROMOTION_STATUS}"

zip_results

if [ "${REQUIRE_PROMOTION}" = "1" ] && [ "${PROMOTION_STATUS}" != "0" ]; then
  log "Promotion gate failed and REQUIRE_PROMOTION=1. Results zip was still written."
  exit "${PROMOTION_STATUS}"
fi

log "complete"
if [ "${RUN_PROFILE}" != "thesis" ]; then
  log "NOTE: PROFILE=${PROFILE} is a T4 development run, not final thesis evidence."
  log "For promotion-eligible output, rerun with PROFILE=thesis."
fi
