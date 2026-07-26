#!/usr/bin/env bash
# Set up the development environment and local hosted-run placeholders on macOS.

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
cd "$REPO_ROOT"

bash scripts/setup_venv.sh

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example; add credentials locally when needed."
else
  echo "Existing .env left unchanged."
fi

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "OPENROUTER_API_KEY is not set; offline checks remain available."
fi
if [[ -z "${LONGMEMEVAL_DATA:-}" ]]; then
  echo "LONGMEMEVAL_DATA is not set; external-data runs remain unavailable."
fi

echo "Run the offline gate with: make check"
