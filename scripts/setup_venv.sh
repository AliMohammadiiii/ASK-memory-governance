#!/usr/bin/env bash
# One-shot venv setup for the M1-W1 work.
#
# Usage (on your Mac, from the repo root):
#   bash scripts/setup_venv.sh
#
# Behavior:
#   1. Creates .venv if missing (Python ≥ 3.11 required by pyproject).
#   2. Activates it.
#   3. Upgrades pip.
#   4. Installs the locked core deps (requirements-lock.txt).
#   5. Installs the package in editable mode (so `import ksa.data...` works
#      without `PYTHONPATH=src`).
#   6. Installs the optional `pai` extra (pydantic-ai), which is small.
#   7. Runs pytest as a smoke check.
#
# What it does NOT install:
#   - The `ml` extra (torch / transformers / accelerate) — multi-GB; install
#     only on the GPU runner via:    pip install -e '.[ml]'
#   - The `accel` extra (bitsandbytes / flash-attn) — same reason.
#   - The `schema` extra (linkml) — only needed to regenerate schema/generated/*.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

# --- 1. Pick Python ----------------------------------------------------- #
PYBIN=""
for cand in python3.12 python3.11 python3; do
    if command -v "$cand" >/dev/null 2>&1; then
        ver="$("$cand" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
        major="${ver%%.*}"; minor="${ver##*.}"
        if [[ "$major" -ge 3 ]] && [[ "$minor" -ge 11 ]]; then
            PYBIN="$cand"; break
        fi
    fi
done
if [[ -z "$PYBIN" ]]; then
    echo "ERROR: no python3.11+ found on PATH (pyproject requires >=3.11)" >&2
    exit 1
fi
echo "[setup] using $($PYBIN --version 2>&1)"

# --- 2. Create / repair .venv ------------------------------------------ #
if [[ ! -d .venv ]]; then
    echo "[setup] creating .venv ..."
    "$PYBIN" -m venv .venv
elif [[ ! -x .venv/bin/python ]]; then
    # Symlinks may be stale (e.g. Homebrew Python rebuilt). Recreate.
    echo "[setup] .venv looks stale; recreating ..."
    rm -rf .venv
    "$PYBIN" -m venv .venv
else
    echo "[setup] reusing existing .venv"
fi

# --- 3. Activate -------------------------------------------------------- #
# shellcheck source=/dev/null
source .venv/bin/activate
echo "[setup] active python: $(which python)"
echo "[setup] active version: $(python --version 2>&1)"

# --- 4. Upgrade pip ----------------------------------------------------- #
python -m pip install --upgrade pip --quiet

# --- 5. Locked core deps ----------------------------------------------- #
echo "[setup] installing locked core deps ..."
python -m pip install -r requirements-lock.txt

# --- 6. Editable package + optional pydantic-ai ------------------------ #
echo "[setup] installing ksa-controller (editable) + pai extra ..."
python -m pip install -e '.[pai,dev]'

# --- 7. Sanity check --------------------------------------------------- #
echo "[setup] running pytest ..."
python -m pytest -q

cat <<EOF

[setup] done.

Next steps:
  source .venv/bin/activate                  # activate when starting a session
  bash scripts/finalize_m1w1.sh              # full M1-W1 finalization
  python scripts/smoke_e2e.py --help         # one-off smoke runs
  python scripts/bench_inference.py --help   # bench (Ollama or HF)

Optional extras (install only if needed):
  pip install -e '.[ml]'     # torch / transformers / accelerate (GPU runner)
  pip install -e '.[accel]'  # bitsandbytes / flash-attn (Linux + CUDA)
  pip install -e '.[schema]' # linkml (only when regenerating schema/generated/*)
EOF
