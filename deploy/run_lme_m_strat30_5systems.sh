#!/usr/bin/env bash
# Legacy filename retained for compatibility. Run only the controller on a
# competency-stratified
# LongMemEval-M slice of 30 questions per competency (6 x 30 = 180 questions),
# 10 shards, capturing full per-question data (answers, tokens, latency,
# judge verdicts, action logs, LLM-call traces) with the v7 fixes plus the v8
# publication-readiness overlay applied.
#
# Prereq: export OPENROUTER_API_KEY=... before running.
#   export OPENROUTER_API_KEY=sk-or-v1-...
#   bash deploy/run_lme_m_strat30_5systems.sh
set -euo pipefail

cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

: "${OPENROUTER_API_KEY:?export OPENROUTER_API_KEY before running}"

PYTHON="${PYTHON:-python3}"
FULL_SLICE="${FULL_SLICE:-data/slices/longmemeval_m_full.jsonl}"
PER_COMPETENCY="${PER_COMPETENCY:-30}"
SEED="${SEED:-0}"
STRAT_SLICE="${STRAT_SLICE:-data/slices/longmemeval_m_strat${PER_COMPETENCY}_seed${SEED}.jsonl}"

# 1) Build the stratified slice (30 per competency) once; reused on re-runs.
if [[ ! -f "${STRAT_SLICE}" ]]; then
  echo "[strat30] building ${STRAT_SLICE} (${PER_COMPETENCY}/competency, seed ${SEED})"
  "${PYTHON}" scripts/build_stratified_slice.py \
    --src "${FULL_SLICE}" --out "${STRAT_SLICE}" \
    --per-competency "${PER_COMPETENCY}" --seed "${SEED}"
else
  echo "[strat30] reusing existing ${STRAT_SLICE}"
fi
ROWS="$("${PYTHON}" - "$STRAT_SLICE" <<'PY'
import sys
print(sum(1 for _ in open(sys.argv[1], encoding="utf-8")))
PY
)"
SAMPLE_TO=$(( ROWS - 1 ))
echo "[strat30] slice rows=${ROWS} -> range 0..${SAMPLE_TO}"

OUT="${OUT:-runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed${SEED}_v8}"

# 2) Run only the contribution (controller) with full data capture.
JUDGE_OPENAI_EXTRA_BODY_JSON='{"provider":{"order":["wandb","venice"],"only":["wandb","venice"],"allow_fallbacks":true},"reasoning":{"enabled":false}}' \
OPENROUTER_API_KEY="${OPENROUTER_API_KEY}" \
OPENAI_API_KEY_ENV=OPENROUTER_API_KEY \
OPENAI_EXTRA_BODY_JSON='{"provider":{"order":["venice","deepinfra","siliconflow"],"only":["venice","deepinfra","siliconflow"],"allow_fallbacks":true},"reasoning":{"enabled":false}}' \
FAST_MODEL=qwen/qwen3.5-9b \
BIG_MODEL=qwen/qwen3.5-9b \
ANSWER_ESCALATION_BASE_URL=https://openrouter.ai/api/v1 \
ANSWER_ESCALATION_MODEL=qwen/qwen3.5-35b-a3b \
JUDGE_MODEL=google/gemma-4-31b-it \
EXTRACTION_MAX_NEW_TOKENS=512 \
RELATION_MAX_NEW_TOKENS=256 \
OPENAI_MAX_MODEL_LEN=32768 \
RETRIEVAL_K=16 \
CONTROLLER_MEMORY_TOP_K=64 \
EXTRACTION_CONCURRENCY=8 \
ANSWER_CONTEXT_MAX_TOKENS=12000 \
V7_FIXES=1 \
V8_FIXES=1 \
HISTORY_RETRIEVAL_K=4 \
ANSWER_CONTEXT_SESSION_CAP=4 \
SHARD_RETRIES=2 \
SHARD_RETRY_BACKOFF_S=5 \
SHARED_EXTRACTION_CACHE="${OUT}/_shared_extraction_cache.jsonl" \
OUT="${OUT}" \
SLICE="${STRAT_SLICE}" \
SAMPLE_FROM=0 SAMPLE_TO="${SAMPLE_TO}" \
SYSTEMS=controller \
SHARDS=10 \
EMBED_MODEL_PATH=sentence-transformers/all-MiniLM-L6-v2 \
EMBED_MODEL_NAME=minilm \
EMBED_DEVICE=cpu \
EMBED_MAX_SEQ_LENGTH=256 \
EMBED_BATCH_SIZE=128 EMBED_CLIENT_BATCH_SIZE=128 \
bash deploy/run_colab_modal_range.sh

echo "[strat30] controller done -> ${OUT}"
echo "[strat30] report: ${OUT}/controller/report.json"
