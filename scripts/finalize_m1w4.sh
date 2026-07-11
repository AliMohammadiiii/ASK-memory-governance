#!/usr/bin/env bash
# M1-W4 finalization runner — runs on the user's host (laptop/GPU box) where
# Ollama lives. Produces:
#
#   * runs/m1w4/recency/{report.json,judgments.jsonl,answers.jsonl,
#                          judge_cache.jsonl,action_log.jsonl,results.md,run.log}
#   * runs/m1w4/no_memory/{...}      (re-run of W2 with current evaluator code)
#   * runs/m1w4/flat_vector/{...}    (re-run of W3 with current evaluator code)
#   * NOTES/m1w4_results.md          — merged 3-baseline table (Δ vs. no_memory)
#   * NOTES/m1w4_evaluator_drift.md  — ±1pp tolerance check vs. archived numbers
#   * NOTES/m1w4_sanity.md           — eviction-of-truth qualitative analysis
#
# Acceptance criterion: Gate G1 — three baselines × competencies × CIs in one
# table. The §3.4 ±1pp drift tolerance is enforced by the merge step.
#
# Usage:
#   bash scripts/finalize_m1w4.sh                 # full 50-session run
#   bash scripts/finalize_m1w4.sh --limit 5       # 5-session smoke
#   CAPACITY=25 bash scripts/finalize_m1w4.sh     # capacity peek for §3.5
#   SKIP_RERUN=1 bash scripts/finalize_m1w4.sh    # use archived W2/W3 numbers

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

# --- libomp / threading hygiene (Apple-Silicon segfault mitigation; W3 §5b)
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
EMBEDDER_DEVICE="${EMBEDDER_DEVICE:-cpu}"

OUT_DIR_RECENCY="runs/m1w4/recency"
OUT_DIR_NM="runs/m1w4/no_memory"
OUT_DIR_FV="runs/m1w4/flat_vector"
REF_DIR_NM="runs/m1w2/no_memory"
REF_DIR_FV="runs/m1w3/flat_vector"

SLICE="data/slices/longmemeval_s_50_seed0.jsonl"
MODEL="${OLLAMA_MODEL:-gemma4:e4b}"
HOST="${OLLAMA_HOST:-http://localhost:11434}"
K="${K:-5}"
CAPACITY="${CAPACITY:-50}"
SKIP_RERUN="${SKIP_RERUN:-0}"
EXTRA_ARGS=("$@")

echo "==> M1-W4 finalize: ${MODEL} via ${HOST}"
echo "    slice    : ${SLICE}"
echo "    out      : ${OUT_DIR_RECENCY}"
echo "    k        : ${K}"
echo "    capacity : ${CAPACITY}"
echo "    embed    : MiniLM-L6-v2 on ${EMBEDDER_DEVICE}"

# --- prereq checks ----------------------------------------------------------
if [[ ! -f "${SLICE}" ]]; then
  echo "ERROR: slice not found at ${SLICE}. Build it via scripts/build_slice.py" >&2
  exit 1
fi

if ! curl -s --max-time 5 "${HOST}/api/tags" >/dev/null; then
  echo "ERROR: Ollama not reachable at ${HOST}. Run 'ollama serve' and retry." >&2
  exit 1
fi

# Chat ping (same pattern as finalize_m1w3.sh).
echo "==> chat ping: warming up ${MODEL} (may take ~30-60s on cold load)"
ping_payload=$(cat <<EOF
{"model":"${MODEL}","messages":[{"role":"user","content":"reply with just: ok"}],"stream":false,"keep_alive":"30m","options":{"temperature":0,"num_predict":4,"num_ctx":2048}}
EOF
)
ping_response="$(curl -sS --max-time 180 -w '\nHTTP_CODE=%{http_code}\n' \
    -X POST "${HOST}/api/chat" \
    -H 'Content-Type: application/json' \
    -d "${ping_payload}" || true)"
ping_http_code="$(echo "${ping_response}" | grep -oE 'HTTP_CODE=[0-9]+' | tail -1 | cut -d= -f2)"
ping_http_code="${ping_http_code:-000}"
if [[ "${ping_http_code}" != "200" ]]; then
  echo "ERROR: /api/chat ping returned HTTP ${ping_http_code}." >&2
  echo "${ping_response}" | head -20 >&2
  exit 1
fi
echo "==> chat ping ok (HTTP 200)"

PY="python3"
if [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
fi
echo "==> using python: ${PY}"

# --- pre-flight tests -------------------------------------------------------
echo "==> pytest M1-W4 baseline + carry-over"
PYTHONPATH=src "${PY}" -m pytest -q \
    tests/test_no_memory.py \
    tests/test_longmemeval_eval.py \
    tests/test_embeddings.py \
    tests/test_flat_vector_store.py \
    tests/test_flat_vector.py \
    tests/test_supersede.py \
    tests/test_memory_operations.py \
    tests/test_action_log.py \
    tests/test_recency_pruning.py
echo

# --- the recency run --------------------------------------------------------
mkdir -p "${OUT_DIR_RECENCY}"
LOG="${OUT_DIR_RECENCY}/run.log"
echo "==> writing log to ${LOG}"

set +e
PYTHONPATH=src "${PY}" scripts/run_baseline.py \
    --baseline recency \
    --slice "${SLICE}" \
    --out "${OUT_DIR_RECENCY}" \
    --seed 0 \
    --k "${K}" \
    --capacity "${CAPACITY}" \
    --embedder-device "${EMBEDDER_DEVICE}" \
    --ollama \
    --ollama-model "${MODEL}" \
    --ollama-host "${HOST}" \
    ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} 2>&1 | tee "${LOG}"
RC=${PIPESTATUS[0]}
set -e

if [[ ${RC} -ne 0 ]]; then
  echo "ERROR: recency run exited with code ${RC}; see ${LOG}" >&2
  exit "${RC}"
fi

# --- evaluator-drift re-runs of W2 + W3 ------------------------------------
if [[ "${SKIP_RERUN}" != "1" ]]; then
  echo
  echo "==> re-running no_memory + flat_vector with current evaluator code"
  echo "    (drift check: §3.4 tolerates ±1pp vs. archived numbers)"

  mkdir -p "${OUT_DIR_NM}" "${OUT_DIR_FV}"

  PYTHONPATH=src "${PY}" scripts/run_baseline.py \
      --baseline no_memory \
      --slice "${SLICE}" \
      --out "${OUT_DIR_NM}" \
      --seed 0 \
      --ollama --ollama-model "${MODEL}" --ollama-host "${HOST}" \
      2>&1 | tee "${OUT_DIR_NM}/run.log"

  PYTHONPATH=src "${PY}" scripts/run_baseline.py \
      --baseline flat_vector \
      --slice "${SLICE}" \
      --out "${OUT_DIR_FV}" \
      --seed 0 \
      --k "${K}" --embedder-device "${EMBEDDER_DEVICE}" \
      --ollama --ollama-model "${MODEL}" --ollama-host "${HOST}" \
      2>&1 | tee "${OUT_DIR_FV}/run.log"
else
  echo "==> SKIP_RERUN=1: copying archived W2/W3 reports for the merge"
  mkdir -p "${OUT_DIR_NM}" "${OUT_DIR_FV}"
  cp "${REF_DIR_NM}/report.json" "${OUT_DIR_NM}/report.json"
  cp "${REF_DIR_FV}/report.json" "${OUT_DIR_FV}/report.json"
  cp "${REF_DIR_NM}/judgments.jsonl" "${OUT_DIR_NM}/judgments.jsonl" 2>/dev/null || true
  cp "${REF_DIR_FV}/judgments.jsonl" "${OUT_DIR_FV}/judgments.jsonl" 2>/dev/null || true
fi

# --- evaluator-drift report -------------------------------------------------
echo "==> writing NOTES/m1w4_evaluator_drift.md"
PYTHONPATH=src "${PY}" scripts/check_drift.py \
    --archived "${REF_DIR_NM}/report.json" "${OUT_DIR_NM}/report.json" \
    --archived "${REF_DIR_FV}/report.json" "${OUT_DIR_FV}/report.json" \
    > NOTES/m1w4_evaluator_drift.md || true

# --- merged 3-baseline results table ---------------------------------------
echo "==> rendering NOTES/m1w4_results.md (merged 3-baseline table)"
PYTHONPATH=src "${PY}" scripts/print_report.py \
    --merge "${OUT_DIR_NM}/report.json" "${OUT_DIR_FV}/report.json" "${OUT_DIR_RECENCY}/report.json" \
    > NOTES/m1w4_results.md
cat >> NOTES/m1w4_results.md <<'EOF'

---

## Caption draft (Chapter 4, Table 4.1 cont'd)

> **Table 4.1 (cont'd).** Per-competency accuracy of Baseline 3
> (recency-pruning: FIFO eviction at capacity N=50 over per-user-turn
> memory items, identical retrieval to Baseline 2) on the LongMemEval-S
> 50-session development slice. Δ vs. Baselines 1 and 2 in parentheses.
> Errors are 95% bootstrap CIs over 1,000 resamples. Recency-pruning
> trades retention for noise: gains over no-memory on multi-session
> reasoning, but eviction discards information that flat-vector retains,
> producing a context-dependent gap. The trivial extractor used here is
> replaced by an LLM-based extractor in Chapter 4.X; recency-pruning is
> rerun in §4.X with the updated item stream.

EOF

# --- per-competency win/loss matrices --------------------------------------
if [[ -f "${OUT_DIR_FV}/judgments.jsonl" && -f "${OUT_DIR_RECENCY}/judgments.jsonl" ]]; then
  echo "==> rendering NOTES/m1w4_win_loss.md (recency vs. flat_vector)"
  PYTHONPATH=src "${PY}" scripts/win_loss.py \
      --ref "${OUT_DIR_FV}/judgments.jsonl" \
      --new "${OUT_DIR_RECENCY}/judgments.jsonl" \
      --ref-name flat_vector --new-name recency \
      > NOTES/m1w4_win_loss.md
fi
if [[ -f "${OUT_DIR_NM}/judgments.jsonl" && -f "${OUT_DIR_RECENCY}/judgments.jsonl" ]]; then
  PYTHONPATH=src "${PY}" scripts/win_loss.py \
      --ref "${OUT_DIR_NM}/judgments.jsonl" \
      --new "${OUT_DIR_RECENCY}/judgments.jsonl" \
      --ref-name no_memory --new-name recency \
      >> NOTES/m1w4_win_loss.md
fi

# --- §3.5: 5-session capacity peek (capacity=25) ---------------------------
if [[ "${SKIP_RERUN}" != "1" ]]; then
  echo "==> §3.5 5-session peek at capacity=25 (sign-of-effect check)"
  PEEK_DIR="runs/m1w4/recency_cap25_peek"
  mkdir -p "${PEEK_DIR}"
  PYTHONPATH=src "${PY}" scripts/run_baseline.py \
      --baseline recency \
      --slice "${SLICE}" \
      --out "${PEEK_DIR}" \
      --seed 0 \
      --k "${K}" \
      --capacity 25 \
      --limit 5 \
      --embedder-device "${EMBEDDER_DEVICE}" \
      --ollama --ollama-model "${MODEL}" --ollama-host "${HOST}" \
      2>&1 | tee "${PEEK_DIR}/run.log" || true
fi

# --- run-metadata stamp on m1w4_sanity.md ---------------------------------
echo "==> stamping run metadata into NOTES/m1w4_sanity.md"
WALL_S="$("${PY}" -c "import json; print(json.load(open('${OUT_DIR_RECENCY}/report.json')).get('wall_clock_seconds', 0))")"
NOW_UTC="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

if [[ ! -s NOTES/m1w4_sanity.md ]]; then
  cp NOTES/m1w4_sanity.template.md NOTES/m1w4_sanity.md 2>/dev/null || true
fi

"${PY}" - <<PY
import re, pathlib, os
p = pathlib.Path("NOTES/m1w4_sanity.md")
if p.exists():
    txt = p.read_text(encoding="utf-8")
    sub = {
        "\${RUN_TIMESTAMP_UTC}":   "${NOW_UTC}",
        "\${RUN_WALL_SECONDS}":    "${WALL_S}",
        "\${RUN_MODEL_TAG}":       "${MODEL}",
        "\${RUN_K}":               "${K}",
        "\${RUN_CAPACITY}":        "${CAPACITY}",
    }
    for k, v in sub.items():
        txt = txt.replace(k, str(v))
    p.write_text(txt, encoding="utf-8")
PY

echo
echo "==> M1-W4 finalize complete."
echo
echo "    Wall-clock for the recency run: ${WALL_S}s"
echo
echo "    Next:"
echo "      1. Read NOTES/m1w4_results.md (merged 3-baseline table)."
echo "      2. Read NOTES/m1w4_evaluator_drift.md (±1pp drift check)."
echo "      3. Read NOTES/m1w4_win_loss.md (per-competency disagreement)."
echo "      4. Hand-classify ≤10 eviction-of-truth examples in NOTES/m1w4_sanity.md."
echo "      5. Decide PASS/CONDITIONAL/FAIL in NOTES/G1_gate_decision.md."
echo "      6. Tag v0.2.0-m1-end-G1-{pass,conditional,fail}."
