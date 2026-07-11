#!/usr/bin/env bash
# Run ALL five systems (controller, b4, b3, b2, b1) on the MGP-6 v2 diagnostic
# in the closed-book two-stage protocol, score each with the repository's own
# metrics_mgp6.py, and emit an analytical report.
#
# These are deterministic, offline reference systems (no LLM / GPU / API key
# required). To score the real LLM-backed controller instead, write its
# predictions to <OUT>/controller/predictions.jsonl in the same format and rerun
# metrics_mgp6.py.
#
#   bash deploy/run_mgp6_v2_5systems.sh
#
# Optional environment overrides:
#   OUT=runs/my_run  GOLD=data/mgp6_v2.jsonl  BOOTSTRAP=1000  SYSTEMS=controller,b4,b3,b2,b1
set -euo pipefail

# cd to the mgp6_v2 directory (parent of this deploy/ folder).
cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

PYTHON="${PYTHON:-python3}"
GOLD="${GOLD:-data/mgp6_v2.jsonl}"
OUT="${OUT:-runs/ref_5systems}"
BOOTSTRAP="${BOOTSTRAP:-1000}"
SYSTEMS="${SYSTEMS:-controller,b4,b3,b2,b1}"

echo "[mgp6-v2] python : $(${PYTHON} --version 2>&1)"
echo "[mgp6-v2] gold   : ${GOLD}"
echo "[mgp6-v2] out    : ${OUT}"
echo "[mgp6-v2] systems: ${SYSTEMS}  (bootstrap=${BOOTSTRAP})"

# 0) Ensure pydantic v2 is importable (only hard dependency).
if ! ${PYTHON} -c "import pydantic" 2>/dev/null; then
  echo "[mgp6-v2] installing pydantic>=2"
  ${PYTHON} -m pip install "pydantic>=2" --quiet --break-system-packages \
    || ${PYTHON} -m pip install "pydantic>=2" --quiet
fi

# 1) Validate the dataset before scoring anything.
echo "[mgp6-v2] validating dataset ..."
${PYTHON} validate_mgp6.py --input "${GOLD}" --strict

# 2) Run all five systems -> predictions.jsonl + report.json each, + summary.json.
echo "[mgp6-v2] running systems ..."
${PYTHON} run_5systems.py \
  --gold "${GOLD}" \
  --out "${OUT}" \
  --bootstrap "${BOOTSTRAP}" \
  --systems "${SYSTEMS}"

# 3) Aggregate into ANALYSIS.md + comparison.json.
echo "[mgp6-v2] building analytical report ..."
${PYTHON} analyze_5systems.py --out "${OUT}"

echo "[mgp6-v2] DONE."
echo "[mgp6-v2] per-system: ${OUT}/{controller,b4,b3,b2,b1}/{predictions.jsonl,report.json}"
echo "[mgp6-v2] report    : ${OUT}/ANALYSIS.md"
echo "[mgp6-v2] tables    : ${OUT}/summary.json , ${OUT}/comparison.json"
