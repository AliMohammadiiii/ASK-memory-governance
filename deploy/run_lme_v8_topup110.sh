#!/usr/bin/env bash
# v8 TOP-UP: run ONLY the ~110 strat30 questions that do NOT yet have v8
# answers (the other 70 were already answered under v8 in the failure-replay
# run). Afterwards, scripts/merge_v8_full180.py re-judges the replay leg with
# the protocol judge (gemma-4-31b) and merges both legs into one full-180
# controller estimate — no failure-selection patching, no manual overrides.
#
# Cheaper than deploy/run_lme_v8_full_5systems.sh (which stays available as
# the strictest option / for the B1-B4 baselines).
#
# Prereq: export OPENROUTER_API_KEY=...
#         export MODAL_ENDPOINT_URL=...
#         export MODAL_KEY=...
#         export MODAL_SECRET=...
#   bash deploy/run_lme_v8_topup110.sh
# Resumable: re-run to continue incomplete shards.
set -euo pipefail

cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  if [[ -f ../.env ]]; then
    OPENROUTER_API_KEY="$(grep '^OPENROUTER_KEY1=' ../.env | cut -d'"' -f2)"
  fi
fi

: "${OPENROUTER_API_KEY:?export OPENROUTER_API_KEY before running}"

PYTHON="${PYTHON:-python3}"
SEED="${SEED:-0}"
STRAT_SLICE="${STRAT_SLICE:-data/slices/longmemeval_m_strat30_seed${SEED}.jsonl}"
REPLAY_RUN="${REPLAY_RUN:-runs/lme_m_modal_qwen35_9b_v8_v7_failures_nothink/controller}"
TOPUP_SLICE="${TOPUP_SLICE:-data/slices/longmemeval_m_strat30_seed${SEED}_v8_topup110.jsonl}"
OUT="${OUT:-runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed${SEED}_v8_topup110}"
MERGED="${MERGED:-runs/lme_m_strat30_seed${SEED}_v8_full180_merged/controller}"

# 1) Derive the top-up slice from the replay run (no hand-kept id lists).
"${PYTHON}" scripts/build_v8_topup_slice.py \
  --slice "${STRAT_SLICE}" --replay-run "${REPLAY_RUN}" --out "${TOPUP_SLICE}"

ROWS="$("${PYTHON}" - "$TOPUP_SLICE" <<'PY'
import sys
print(sum(1 for _ in open(sys.argv[1], encoding="utf-8")))
PY
)"
SAMPLE_TO=$(( ROWS - 1 ))
echo "[topup] rows=${ROWS} -> range 0..${SAMPLE_TO}"

# 2) Configured for Modal Qwen 3.5 9B answerer and OpenRouter Gemma-4-31B-It judge.
#    Since we are top-upping the failures run leg, escalation is disabled.
OPENROUTER_API_KEY="${OPENROUTER_API_KEY}" \
OPENAI_API_KEY_ENV=OPENROUTER_API_KEY \
OPENAI_EXTRA_BODY_JSON='{"provider":{"order":["venice","deepinfra","siliconflow"],"only":["venice","deepinfra","siliconflow"],"allow_fallbacks":true},"reasoning":{"enabled":false}}' \
FAST_MODEL=qwen/qwen3.5-9b \
BIG_MODEL=qwen/qwen3.5-9b \
ANSWER_ESCALATION_BASE_URL="" \
ANSWER_ESCALATION_MODEL="" \
JUDGE_MODEL=google/gemma-4-31b-it \
JUDGE_OPENAI_BASE_URL=https://openrouter.ai/api/v1 \
JUDGE_OPENAI_API_KEY_ENV=OPENROUTER_API_KEY \
JUDGE_OPENAI_EXTRA_BODY_JSON='{"provider":{"order":["wandb","venice"],"only":["wandb","venice"],"allow_fallbacks":true},"reasoning":{"enabled":false}}' \
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
SLICE="${TOPUP_SLICE}" \
SAMPLE_FROM=0 SAMPLE_TO="${SAMPLE_TO}" \
SYSTEMS="${SYSTEMS:-controller}" \
SHARDS="${SHARDS:-10}" \
EMBED_MODEL_PATH=sentence-transformers/all-MiniLM-L6-v2 \
EMBED_MODEL_NAME=minilm \
EMBED_DEVICE=cpu \
EMBED_MAX_SEQ_LENGTH=256 \
EMBED_BATCH_SIZE=128 EMBED_CLIENT_BATCH_SIZE=128 \
bash deploy/run_colab_modal_range.sh

echo "[topup] done -> ${OUT}/controller/report.json"

# 3) Merge: 110 fresh v8 + 70 replay v8 answers, ONE judge (re-judged),
#    machine verdicts only.
"${PYTHON}" scripts/merge_v8_full180.py \
  --slice "${STRAT_SLICE}" \
  --topup-run "${OUT}/controller" \
  --replay-run "${REPLAY_RUN}" \
  --out "${MERGED}"

echo "[topup] merged full-180 diagnostic construction -> ${MERGED}/report.json"
echo "[topup] compare vs ineligible carry-forward construction:"
echo "  python scripts/win_loss.py \\"
echo "    --ref runs/lme_m_v8_failure_replay_adjudicated/controller/judgments.jsonl \\"
echo "    --new ${MERGED}/judgments.jsonl \\"
echo "    --ref-name v8_adjudicated --new-name v8_full180_merged"
