#!/usr/bin/env bash
# Judge primary/fallback confound audit over a run's judgments.jsonl files.
# Wraps scripts/analysis/judge_audit.py. Offline; read-only.
#
# Reports, per system and combined: model/scoring fallback rate, accuracy split,
# and per-competency fallback rate. Under final-2.0 the expected model-fallback
# count is zero because google/gemma-4-31b-it is the only judge route.
#
# Usage:
#   bash scripts/evaluation/run_judge_audit.sh [RUN_ROOT]
#   # default RUN_ROOT = runs_local/lme_final_5systems_v12_qwen_180
#
# macOS-compatible; python3 only.
set -euo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
cd "$REPO"

PYTHON="${PYTHON:-python3}"
if [ -x .venv/bin/python ]; then PYTHON=".venv/bin/python"; fi

RUN_ROOT="${1:-runs_local/lme_final_5systems_v12_qwen_180}"
OUT_DIR="runs_local/judge_audit"
OUT_JSON="$OUT_DIR/$(basename "$RUN_ROOT")_judge_audit.json"

echo "[judge-audit] analyzer : scripts/analysis/judge_audit.py"
echo "[judge-audit] run root  : $RUN_ROOT"
echo "[judge-audit] fields    : judge_model_id, used_fallback, correct, competency"

if [ ! -d "$RUN_ROOT" ]; then
  echo "[judge-audit] ERROR: run root '$RUN_ROOT' not found." >&2
  exit 1
fi
COUNT="$(find "$RUN_ROOT" -name judgments.jsonl 2>/dev/null | wc -l | tr -d ' ')"
if [ "$COUNT" -eq 0 ]; then
  echo "[judge-audit] ERROR: no judgments.jsonl under '$RUN_ROOT'." >&2
  exit 1
fi
echo "[judge-audit] found $COUNT judgments.jsonl file(s)"

mkdir -p "$OUT_DIR"
"$PYTHON" scripts/analysis/judge_audit.py --run-root "$RUN_ROOT" --out "$OUT_JSON"
echo "[judge-audit] wrote $OUT_JSON"
