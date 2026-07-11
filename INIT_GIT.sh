#!/usr/bin/env bash
set -euo pipefail

if [[ -d .git ]]; then
  echo "Git is already initialized."
  exit 0
fi

git init -b main
git add .
echo "Repository initialized. Configure your Git identity, then run:"
echo "  git commit -m 'Initial public KSA memory governance repository'"
