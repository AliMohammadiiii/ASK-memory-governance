#!/usr/bin/env bash
set -euo pipefail

# Serial LongMemEval-S test bundle: b1, b2, b3, b4, then controller.
#
# This is the safest one-command path when the next decision depends on a
# readable baseline-vs-controller table rather than fastest wall-clock time.
# It delegates to the validated 50-session runner with MAX_WORKERS=1, so the
# same strict validation, summary generation, resume behavior, and result zip
# are used.

usage() {
  cat <<'EOF'
Usage:
  bash deploy/run_colab_m4w13_serial_final.sh [SYSTEMS] [runner args...]

SYSTEMS can be:
  all
  b1
  b2
  b3
  b4
  controller
  b1,controller

Examples:
  bash deploy/run_colab_m4w13_serial_final.sh
  bash deploy/run_colab_m4w13_serial_final.sh b1
  bash deploy/run_colab_m4w13_serial_final.sh controller
  bash deploy/run_colab_m4w13_serial_final.sh b1,controller --dry-run
  PROFILE=quality bash deploy/run_colab_m4w13_serial_final.sh controller
  SEED=0 bash deploy/run_colab_m4w13_serial_final.sh b1

Environment overrides still work:
  SYSTEMS=controller OUT=runs/my_controller bash deploy/run_colab_m4w13_serial_final.sh
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

PROFILE="${PROFILE:-balanced}" # balanced | quality
LIMIT="${LIMIT:-50}"
SEED="${SEED:-0}"
N_BOOTSTRAP="${N_BOOTSTRAP:-1000}"
SLICE="${SLICE:-data/slices/longmemeval_s_cleaned_50_seed0.jsonl}"
MAX_WORKERS="${MAX_WORKERS:-1}"
REQUIRE_A100="${REQUIRE_A100:-0}"
CLEAN_INCOMPLETE="${CLEAN_INCOMPLETE:-0}"
NO_PREFETCH="${NO_PREFETCH:-0}"
export PYTHONHASHSEED="${PYTHONHASHSEED:-0}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"

if [ "$#" -gt 0 ] && [[ "${1}" != -* ]]; then
  SYSTEMS="${1}"
  shift
else
  SYSTEMS="${SYSTEMS:-all}"
fi

IFS=',' read -r -a _requested_systems <<< "${SYSTEMS}"
for _system in "${_requested_systems[@]}"; do
  case "${_system}" in
    all|b1|b2|b3|b4|controller|no_memory|flat_vector|recency|naive_overwrite)
      ;;
    *)
      echo "unknown SYSTEMS entry: ${_system}" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "${OUT+x}" ]; then
  if [ "${SYSTEMS}" = "all" ]; then
    OUT="runs/m4w13_serial_${PROFILE}"
  else
    SYSTEMS_SLUG="$(printf '%s' "${SYSTEMS}" | tr ',' '_' | tr -cd '[:alnum:]_-')"
    OUT="runs/m4w13_serial_${PROFILE}_${SYSTEMS_SLUG}"
  fi
fi

export PROFILE
export SYSTEMS
export LIMIT
export SEED
export N_BOOTSTRAP
export SLICE
export OUT
export MAX_WORKERS
export REQUIRE_A100
export CLEAN_INCOMPLETE
export NO_PREFETCH

if [ "${SYSTEMS}" = "all" ]; then
  echo "[m4w13-serial-final] sequence: b1 -> b2 -> b3 -> b4 -> controller"
else
  echo "[m4w13-serial-final] selected systems: ${SYSTEMS}"
fi
echo "[m4w13-serial-final] profile=${PROFILE} limit=${LIMIT} out=${OUT}"
echo "[m4w13-serial-final] seed=${SEED} n_bootstrap=${N_BOOTSTRAP} pythonhashseed=${PYTHONHASHSEED}"

bash deploy/run_colab_m4w13_50_cache.sh "$@"
