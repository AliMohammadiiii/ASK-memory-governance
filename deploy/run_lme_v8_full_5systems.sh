#!/usr/bin/env bash
# FULL HOMOGENEOUS LongMemEval-M v8 rerun: all five systems
# (controller, b4, b3, b2, b1) on the SAME 180-question stratified slice,
# in ONE configuration (same models, prompts, seed, judge), NO failure-replay
# patching and NO manual adjudication. This is the paper-grade run that
# replaces the v7-base + v8-failure-replay merged estimate.
#
# Differences vs deploy/run_lme_m_strat30_5systems.sh (which runs controller
# only): SYSTEMS covers all five systems and OUT is a fresh _v8_full5 dir.
# Everything else (models, judge, v7+v8 fixes, retrieval params, embedder)
# is pinned identically.
#
# Prereq: export OPENROUTER_API_KEY=... before running.
#   bash deploy/run_lme_v8_full_5systems.sh
#
# Resumable: re-running continues incomplete shards (cascade resume).
# After it finishes, verify homogeneity + coverage:
#   python scripts/verify_homogeneous_run.py \
#     --run-root runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v8_full5 \
#     --slice data/slices/longmemeval_m_strat30_seed0.jsonl
set -euo pipefail

cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

: "${OPENROUTER_API_KEY:?export OPENROUTER_API_KEY before running}"

PYTHON="${PYTHON:-python3}"
FULL_SLICE="${FULL_SLICE:-data/slices/longmemeval_m_full.jsonl}"
PER_COMPETENCY="${PER_COMPETENCY:-30}"
SEED="${SEED:-0}"
STRAT_SLICE="${STRAT_SLICE:-data/slices/longmemeval_m_strat${PER_COMPETENCY}_seed${SEED}.jsonl}"

# 1) Reuse (or build once) the exact same stratified slice as v7/v8.
if [[ ! -f "${STRAT_SLICE}" ]]; then
  echo "[v8full] building ${STRAT_SLICE} (${PER_COMPETENCY}/competency, seed ${SEED})"
  "${PYTHON}" scripts/build_stratified_slice.py \
    --src "${FULL_SLICE}" --out "${STRAT_SLICE}" \
    --per-competency "${PER_COMPETENCY}" --seed "${SEED}"
else
  echo "[v8full] reusing existing ${STRAT_SLICE}"
fi
ROWS="$("${PYTHON}" - "$STRAT_SLICE" <<'PY'
import sys
print(sum(1 for _ in open(sys.argv[1], encoding="utf-8")))
PY
)"
SAMPLE_TO=$(( ROWS - 1 ))
echo "[v8full] slice rows=${ROWS} -> range 0..${SAMPLE_TO}"

OUT="${OUT:-runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed${SEED}_v8_full5}"
SYSTEMS="${SYSTEMS:-controller,b4,b3,b2,b1}"

# 2) One homogeneous pass over ALL systems (identical config to the v8
#    controller run; only SYSTEMS/OUT differ).
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
SYSTEMS="${SYSTEMS}" \
SHARDS="${SHARDS:-10}" \
EMBED_MODEL_PATH=sentence-transformers/all-MiniLM-L6-v2 \
EMBED_MODEL_NAME=minilm \
EMBED_DEVICE=cpu \
EMBED_MAX_SEQ_LENGTH=256 \
EMBED_BATCH_SIZE=128 EMBED_CLIENT_BATCH_SIZE=128 \
bash deploy/run_colab_modal_range.sh

echo "[v8full] all systems done -> ${OUT}"

# 3) Combined report + homogeneity/coverage gate.
echo "[v8full] merged report:"
REPORTS=()
IFS=',' read -ra SYS_ARR <<< "${SYSTEMS}"
for S in "${SYS_ARR[@]}"; do
  [[ -f "${OUT}/${S}/report.json" ]] && REPORTS+=("${OUT}/${S}/report.json")
done
"${PYTHON}" scripts/print_report.py --merge "${REPORTS[@]}" || true

"${PYTHON}" scripts/verify_homogeneous_run.py \
  --run-root "${OUT}" --slice "${STRAT_SLICE}" --systems "${SYSTEMS}" \
  --expected-n "${ROWS}"

echo "[v8full] NEXT: paired comparison vs the adjudicated estimate:"
echo "  python scripts/win_loss.py \\"
echo "    --ref runs/lme_m_v8_failure_replay_adjudicated/controller/judgments.jsonl \\"
echo "    --new ${OUT}/controller/judgments.jsonl \\"
echo "    --ref-name v8_adjudicated --new-name v8_full"
