#!/usr/bin/env bash
# Canonical controller-only entry point. The target script keeps its historical
# filename so existing notebooks and Colab commands do not break.
set -euo pipefail

cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
exec bash deploy/run_lme_m_strat30_5systems.sh "$@"
