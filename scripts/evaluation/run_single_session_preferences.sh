#!/usr/bin/env bash
# Single-session-preference (SSP) evaluation on a completed run's outputs.
# Wraps scripts/evaluation/evaluate_single_session_preferences.py (the real
# evaluator) with a stratified percentile bootstrap 95% CI (n=20000, seed 0).
#
# Offline: reads the run's judgments.jsonl (+ optional slice) already on disk.
# The contaminated v7 diagnostic reference is SSP 11/30; this reports accuracy + CI for
# whatever run you point it at (e.g. the frozen homogeneous rerun's controller).
#
# Usage:
#   bash scripts/evaluation/run_single_session_preferences.sh \
#       [RUN_CONTROLLER_DIR] [SLICE]
#   # defaults:
#   #   RUN_CONTROLLER_DIR = runs_local/lme_final_5systems_180/controller
#   #   SLICE (optional)   = runs_local/lme_final_5systems_180/range_0_179.jsonl
#
# macOS-compatible; python3 only.
set -euo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
cd "$REPO"

PYTHON="${PYTHON:-python3}"
if [ -x .venv/bin/python ]; then PYTHON=".venv/bin/python"; fi

RUN_DIR="${1:-runs_local/lme_final_5systems_180/controller}"
SLICE="${2:-runs_local/lme_final_5systems_180/range_0_179.jsonl}"
N_BOOT="${N_BOOT:-20000}"
SEED="${SEED:-0}"

OUT_ROOT="runs_local/ssp_eval"
mkdir -p "$OUT_ROOT"
OUT_JSON="$OUT_ROOT/ssp_$(basename "$(dirname "$RUN_DIR")")_$(basename "$RUN_DIR").json"

echo "[ssp] evaluator : scripts/evaluation/evaluate_single_session_preferences.py"
echo "[ssp] run dir   : $RUN_DIR"
echo "[ssp] bootstrap : n=$N_BOOT seed=$SEED (stratified percentile)"
echo "[ssp] reference : contaminated v7 SSP = 11/30 (36.7%), CI [0.20, 0.53]"
echo "[ssp] top-up    : incomplete attempt = 8/29 observed, one unresolved (max 9/30)"

if [ ! -f "$RUN_DIR/judgments.jsonl" ]; then
  echo "[ssp] ERROR: $RUN_DIR/judgments.jsonl not found." >&2
  echo "[ssp] Run scripts/evaluation/run_longmemeval_final.sh --full first." >&2
  exit 1
fi

ARGS=(--run-dir "$RUN_DIR" --n-bootstrap "$N_BOOT" --seed "$SEED")
if [ -f "$SLICE" ]; then
  ARGS+=(--slice "$SLICE")
  echo "[ssp] slice     : $SLICE (SSP set defined by slice, intersected with judged rows)"
else
  echo "[ssp] slice     : (none; SSP set inferred from judgments' competency field)"
fi

# Human-readable to stdout ...
"$PYTHON" scripts/evaluation/evaluate_single_session_preferences.py "${ARGS[@]}"

# ... and an atomic JSON summary to disk.
TMP="$OUT_JSON.tmp"
"$PYTHON" scripts/evaluation/evaluate_single_session_preferences.py "${ARGS[@]}" --json > "$TMP"
mv "$TMP" "$OUT_JSON"
echo "[ssp] wrote $OUT_JSON"
echo "[ssp] NOTE: SSP-specific rates (unsupported-preference, cross-person contamination)"
echo "[ssp] are defined in FINAL_METRIC_DEFINITIONS.md sec F and require the PROPOSED"
echo "[ssp] correction code (not yet implemented) to compute."
