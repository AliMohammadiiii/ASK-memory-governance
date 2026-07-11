#!/usr/bin/env bash
# Build the full 500-question slice from an ALREADY-DOWNLOADED cleaned release.
# No download. Run once per dataset.
#
#   DATASET=s SRC=~/longmemeval/longmemeval_s_cleaned.json bash deploy/build_full_slice.sh
#   DATASET=m SRC=~/longmemeval/longmemeval_m_cleaned.json bash deploy/build_full_slice.sh
set -euo pipefail
cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
[ -f .venv/bin/activate ] && source .venv/bin/activate
export PYTHONPATH="src:${PYTHONPATH:-}"

DATASET="${DATASET:-s}"
SRC="${SRC:-$HOME/longmemeval/longmemeval_${DATASET}_cleaned.json}"
OUT="${OUT:-data/slices/longmemeval_${DATASET}_full.jsonl}"

[ -f "${SRC}" ] || { echo "[build] ERROR: source not found: ${SRC}  (set SRC=...)"; exit 1; }
python scripts/build_slice.py --in "${SRC}" --out "${OUT}" --n all
echo "[build] wrote ${OUT}"
