#!/usr/bin/env bash
# Regenerate reports/FINAL_RESULTS.{md,json} deterministically from the ledger.
# Thin wrapper over scripts/analysis/build_final_results.py (stdlib only; offline).
#
# The ledger (artifacts/results_ledger.json) is a READ-ONLY input and is never
# modified. Re-running on an unchanged ledger produces byte-identical output.
#
# Usage:
#   bash scripts/analysis/build_final_results.sh
#
# macOS-compatible; python3 only.
set -euo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
cd "$REPO"

PYTHON="${PYTHON:-python3}"
if [ -x .venv/bin/python ]; then PYTHON=".venv/bin/python"; fi

LEDGER="${LEDGER:-artifacts/results_ledger.json}"
OUT_DIR="${OUT_DIR:-reports}"

echo "[final-results] ledger : $LEDGER (read-only)"
echo "[final-results] out dir: $OUT_DIR"

if [ ! -f "$LEDGER" ]; then
  echo "[final-results] ERROR: ledger not found: $LEDGER" >&2
  exit 1
fi

"$PYTHON" scripts/analysis/build_final_results.py --ledger "$LEDGER" --out-dir "$OUT_DIR"

echo "[final-results] generated:"
echo "  $OUT_DIR/FINAL_RESULTS.md"
echo "  $OUT_DIR/FINAL_RESULTS.json"
