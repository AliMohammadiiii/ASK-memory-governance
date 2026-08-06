#!/usr/bin/env bash
set -euo pipefail

if command -v python >/dev/null 2>&1; then
  python_executable="python"
elif [[ -x .venv/bin/python ]]; then
  python_executable=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  python_executable="python3"
else
  echo "pre-commit requires Python; run 'make setup' in an activated environment" >&2
  exit 1
fi

exec "${python_executable}" "$@"
