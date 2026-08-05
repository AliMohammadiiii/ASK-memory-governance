#!/usr/bin/env bash
# Create the supported local development environment.

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
cd "$REPO_ROOT"

git submodule update --init --recursive

PYTHON_BIN="${ASK_PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
      "$candidate" -c 'import sys; raise SystemExit(not ((3, 11) <= sys.version_info < (3, 13)))'; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi

if [[ -z "$PYTHON_BIN" ]]; then
  echo "ERROR: Python 3.11 or 3.12 is required (3.13+ is not yet supported)." >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(not ((3, 11) <= sys.version_info < (3, 13)))'; then
  echo "ERROR: ASK_PYTHON must point to Python 3.11 or 3.12." >&2
  exit 1
fi

if [[ -e .venv && ! -x .venv/bin/python ]]; then
  echo "ERROR: .venv exists but is not usable; move it aside and rerun." >&2
  exit 1
fi
if [[ -x .venv/bin/python ]] &&
  ! .venv/bin/python -c 'import sys; raise SystemExit(not ((3, 11) <= sys.version_info < (3, 13)))'; then
  echo "ERROR: existing .venv does not use Python 3.11 or 3.12; move it aside and rerun." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'

echo "Environment ready: $REPO_ROOT/.venv"
echo "Activate with: source .venv/bin/activate"
echo "Verify with:  make check"
