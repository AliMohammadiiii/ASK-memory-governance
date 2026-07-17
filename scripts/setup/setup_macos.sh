#!/usr/bin/env bash
# macOS setup for the KSA final-evaluation laptop workflow.
#   - creates .venv (Python >= 3.11, required by pyproject)
#   - installs the package editable + dev extra
#   - copies .env.example -> .env if .env is absent (NEVER writes secrets)
#   - checks that the required keys are present (does not print their values)
#
# Usage:
#   bash scripts/setup/setup_macos.sh
#
# macOS-compatible: no GNU-only flags; python3 only.
set -euo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
cd "$REPO"

echo "[setup] repo: $REPO"

# --- 1. Pick a Python >= 3.11 ------------------------------------------- #
PYBIN=""
for cand in python3.12 python3.11 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    ver="$("$cand" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    maj="${ver%%.*}"; min="${ver##*.}"
    if [ "$maj" -ge 3 ] && [ "$min" -ge 11 ]; then PYBIN="$cand"; break; fi
  fi
done
if [ -z "$PYBIN" ]; then
  echo "[setup] ERROR: no python3.11+ on PATH (pyproject requires >=3.11)." >&2
  echo "[setup] Install e.g. 'brew install python@3.12' and re-run." >&2
  exit 1
fi
echo "[setup] using $("$PYBIN" --version 2>&1)"

# --- 2. Create / reuse venv --------------------------------------------- #
if [ ! -x .venv/bin/python ]; then
  echo "[setup] creating .venv ..."
  rm -rf .venv
  "$PYBIN" -m venv .venv
else
  echo "[setup] reusing existing .venv"
fi
# shellcheck source=/dev/null
source .venv/bin/activate
echo "[setup] active python: $(python --version 2>&1)"

# --- 3. Install package ------------------------------------------------- #
python -m pip install --upgrade pip >/dev/null
echo "[setup] installing package (editable) + dev extra ..."
python -m pip install -e '.[dev]'
echo "[setup] (optional, only for actual model runs) install ML extra with:"
echo "        pip install -e '.[ml]'   # torch/transformers/sentence-transformers"

# --- 4. .env scaffold (no secrets written) ------------------------------ #
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "[setup] copied .env.example -> .env  (fill in OPENROUTER_API_KEY yourself)"
  else
    echo "[setup] WARNING: no .env.example to copy"
  fi
else
  echo "[setup] .env already present (left untouched)"
fi

# --- 5. Key presence check (values never printed) ----------------------- #
# Load .env into this shell without echoing values.
if [ -f .env ]; then set -a; . ./.env; set +a; fi
MISSING=0
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo "[setup] CHECK: OPENROUTER_API_KEY is NOT set (required for hosted runs)."
  echo "        Put a ROTATED key in .env before LongMemEval / SSP / judge runs."
  MISSING=1
else
  echo "[setup] CHECK: OPENROUTER_API_KEY is present."
fi
if [ -z "${LONGMEMEVAL_DATA:-}" ]; then
  echo "[setup] CHECK: LONGMEMEVAL_DATA not set (path to longmemeval_m_full.jsonl)."
  echo "        Required only for the LongMemEval rerun; offline steps do not need it."
fi

echo "[setup] done. Next: bash scripts/smoke/run_all_smoke_tests.sh"
[ "$MISSING" -eq 0 ] || echo "[setup] (setup succeeded; the missing key is only needed for hosted runs)"
