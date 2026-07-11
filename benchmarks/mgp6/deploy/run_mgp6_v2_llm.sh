#!/usr/bin/env bash
# Run the REAL LLM-backed controller on MGP-6 v2 via an OpenAI-compatible API
# (default OpenRouter qwen/qwen3.5-9b), score it, and rebuild the combined
# report next to the offline baselines.
#
# Prereq: export OPENROUTER_API_KEY=... before running.
#   export OPENROUTER_API_KEY=sk-or-...
#   bash deploy/run_mgp6_v2_llm.sh
#
# The runner is resumable: re-running continues from where it left off, so it
# is safe to interrupt. Optional overrides:
#   MGP6_MODEL=qwen/qwen3.5-9b  MGP6_CONCURRENCY=16  OUT=runs/llm_qwen35_9b
#   REF=runs/ref_5systems  (offline baselines to compare against)
set -euo pipefail
cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

: "${OPENROUTER_API_KEY:?export OPENROUTER_API_KEY before running}"

PYTHON="${PYTHON:-python3}"
GOLD="${GOLD:-data/mgp6_v2.jsonl}"
OUT="${OUT:-runs/llm_${MGP6_MODEL_TAG:-qwen35_9b}}"
REF="${REF:-runs/ref_5systems}"
BOOTSTRAP="${BOOTSTRAP:-1000}"
export MGP6_MODEL="${MGP6_MODEL:-qwen/qwen3.5-9b}"
export MGP6_CONCURRENCY="${MGP6_CONCURRENCY:-16}"

echo "[llm] model=${MGP6_MODEL} out=${OUT}"

# 1) Generate predictions (resumable; loops until the corpus is complete).
while :; do
  ${PYTHON} run_llm_controller.py --gold "${GOLD}" --out "${OUT}/controller" --limit 60
  total=$(wc -l < "${OUT}/controller/predictions.jsonl" | tr -d ' ')
  want=$(wc -l < "${GOLD}" | tr -d ' ')
  echo "[llm] progress ${total}/${want}"
  [[ "${total}" -ge "${want}" ]] && break
done

# 2) Score with the repository scorer.
${PYTHON} metrics_mgp6.py --gold "${GOLD}" \
  --pred "${OUT}/controller/predictions.jsonl" \
  --bootstrap "${BOOTSTRAP}" > "${OUT}/controller/report.json"
echo "[llm] report -> ${OUT}/controller/report.json"

# 3) Rebuild the combined report if the offline baselines exist.
if [[ -f "${REF}/b1/report.json" ]]; then
  ${PYTHON} analyze_all.py --out runs/combined \
    --system b1:"B1 no-memory":"${REF}/b1/report.json" \
    --system b2:"B2 flat-retr.":"${REF}/b2/report.json" \
    --system b3:"B3 recency":"${REF}/b3/report.json" \
    --system b4:"B4 overwrite":"${REF}/b4/report.json" \
    --system ctl_ref:"Controller (rules)":"${REF}/controller/report.json" \
    --system ctl_llm:"Controller (${MGP6_MODEL})":"${OUT}/controller/report.json"
  echo "[llm] combined report -> runs/combined/ANALYSIS.md"
fi
echo "[llm] DONE."
