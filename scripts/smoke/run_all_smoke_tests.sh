#!/usr/bin/env bash
# Offline smoke tests: fast unit subset + data schema validation + a tiny
# offline MGP-6 dry-run. NO network and NO hosted models required.
#
# Usage:
#   bash scripts/smoke/run_all_smoke_tests.sh
#
# macOS-compatible; python3 only.
set -euo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
cd "$REPO"

PYTHON="${PYTHON:-python3}"
if [ -x .venv/bin/python ]; then PYTHON=".venv/bin/python"; fi
echo "[smoke] python: $($PYTHON --version 2>&1)"

FAIL=0

echo "[smoke] 1/3 fast unit test subset (not slow, not network) ..."
if "$PYTHON" -m pytest -q -m 'not slow and not network' ; then
  echo "[smoke] unit subset: PASS"
else
  echo "[smoke] unit subset: FAIL"; FAIL=1
fi

echo "[smoke] 2/3 MGP-6 v2 data schema validation (strict) ..."
if "$PYTHON" benchmarks/mgp6/validate_mgp6.py \
     --input benchmarks/mgp6/data/mgp6_v2.jsonl --strict ; then
  echo "[smoke] validate-data: PASS"
else
  echo "[smoke] validate-data: FAIL"; FAIL=1
fi

echo "[smoke] 3/3 offline 2-item MGP-6 dry-run (no models called) ..."
if "$PYTHON" benchmarks/mgp6/smoke_v2.py \
     --input benchmarks/mgp6/data/mgp6_v2.jsonl \
     --system b1 --limit 2 ; then
  echo "[smoke] mgp6 dry-run: PASS"
else
  echo "[smoke] mgp6 dry-run: FAIL"; FAIL=1
fi

if [ "$FAIL" -eq 0 ]; then
  echo "[smoke] ALL OFFLINE SMOKE CHECKS PASSED"
else
  echo "[smoke] one or more smoke checks FAILED (see output above)"; exit 1
fi
