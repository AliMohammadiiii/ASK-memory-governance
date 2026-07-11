#!/usr/bin/env bash
# M1-W2 finalization runner — runs on the user's host (laptop) where Ollama lives.
#
# Prereqs (verified at start):
#   * `ollama` daemon up (default localhost:11434)
#   * model tag pulled: `ollama pull gemma4:e4b`
#   * repo at v0.1.0-m1w1 (clean working tree expected; this script writes
#     under runs/ and NOTES/ which are git-tracked outputs)
#
# Outputs:
#   * runs/m1w2/no_memory/{report.json,judgments.jsonl,answers.jsonl,
#                          judge_cache.jsonl,results.md,run.log}
#   * NOTES/m1w2_results.md  — overwritten with the real per-competency table
#   * NOTES/m1w2_status.md   — short status note for the advisor
#
# Acceptance criterion: the run completes in < 90 minutes (M1-W2 §5).
#
# Usage:
#   bash scripts/finalize_m1w2.sh                # full 50-session run
#   bash scripts/finalize_m1w2.sh --limit 5      # smoke a 5-session subset

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

OUT_DIR="runs/m1w2/no_memory"
SLICE="data/slices/longmemeval_s_50_seed0.jsonl"
MODEL="${OLLAMA_MODEL:-gemma4:e4b}"
HOST="${OLLAMA_HOST:-http://localhost:11434}"
EXTRA_ARGS=("$@")

echo "==> M1-W2 finalize: ${MODEL} via ${HOST}"
echo "    slice: ${SLICE}"
echo "    out  : ${OUT_DIR}"

# --- prereq checks ------------------------------------------------------------
if [[ ! -f "${SLICE}" ]]; then
  echo "ERROR: slice not found at ${SLICE}. Build it via scripts/build_slice.py" >&2
  exit 1
fi

if ! curl -s --max-time 5 "${HOST}/api/tags" >/dev/null; then
  echo "ERROR: Ollama not reachable at ${HOST}. Run 'ollama serve' and retry." >&2
  exit 1
fi

if ! curl -s "${HOST}/api/tags" | grep -q "\"${MODEL}\""; then
  echo "WARN: model ${MODEL} not visible at /api/tags. If this fails, run 'ollama pull ${MODEL}'."
fi

# /api/tags returning 200 only proves the daemon is up. The model may still
# fail to load on /api/chat (cold-start 502 / 503, missing manifest blob,
# OOM). A real chat ping forces the runner to actually load the model and
# exposes those failures BEFORE the 50-session loop sinks 24 minutes into
# them.
echo "==> chat ping: warming up ${MODEL} (may take ~30-60s on the first cold load)"
# Important: pass keep_alive and num_ctx so the model stays loaded with the
# same KV-cache configuration that run_baseline.py will use. Without this,
# Ollama may unload the model between the ping and the run, or reload it
# with a different num_ctx, forcing a second cold start.
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
  echo "       Body (head):" >&2
  echo "${ping_response}" | head -20 >&2
  echo "" >&2
  echo "       Common causes and fixes:" >&2
  echo "         1. Model not pulled or partial download:" >&2
  echo "              ollama rm ${MODEL} && ollama pull ${MODEL}" >&2
  echo "         2. Daemon needs a restart (corrupted manifest cache):" >&2
  echo "              pkill -f 'ollama serve'; ollama serve &" >&2
  echo "         3. Hardware headroom — model is too large for available RAM:" >&2
  echo "              gemma4:e4b needs ~10 GiB. On an 8 GiB Mac, fall back to" >&2
  echo "              a smaller tag for M1-W2 dev work:" >&2
  echo "                OLLAMA_MODEL=qwen2.5:3b-instruct bash scripts/finalize_m1w2.sh" >&2
  echo "                OLLAMA_MODEL=gemma3:1b           bash scripts/finalize_m1w2.sh" >&2
  echo "              Document the fallback in NOTES/m1w2_results.md." >&2
  exit 1
fi
echo "==> chat ping ok (HTTP 200); proceeding to 50-session run"

# Pick a python that has our deps. Prefer the .venv if it has one.
PY="python3"
if [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
fi
echo "==> using python: ${PY}"

# --- ensure deps present (M1-W2 added Jinja2; older venvs lack it) -----------
ensure_module() {
  local module="$1"
  local pip_spec="$2"
  if ! "${PY}" -c "import ${module}" >/dev/null 2>&1; then
    echo "==> installing missing dep: ${pip_spec}"
    "${PY}" -m pip install --quiet "${pip_spec}"
  fi
}
ensure_module jinja2 "Jinja2>=3.1,<4"
ensure_module pytest "pytest==9.0.3"

# --- pre-flight tests ---------------------------------------------------------
echo "==> pytest sanity (skip if you trust the previous green run)"
PYTHONPATH=src "${PY}" -m pytest -q tests/test_no_memory.py tests/test_longmemeval_eval.py
echo

# --- the actual run -----------------------------------------------------------
mkdir -p "${OUT_DIR}"
LOG="${OUT_DIR}/run.log"
echo "==> writing log to ${LOG}"

set +e
PYTHONPATH=src "${PY}" scripts/run_baseline.py \
    --baseline no_memory \
    --slice "${SLICE}" \
    --out "${OUT_DIR}" \
    --seed 0 \
    --ollama \
    --ollama-model "${MODEL}" \
    --ollama-host "${HOST}" \
    ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} 2>&1 | tee "${LOG}"
RC=${PIPESTATUS[0]}
set -e

if [[ ${RC} -ne 0 ]]; then
  echo "ERROR: run_baseline.py exited with code ${RC}; see ${LOG}" >&2
  exit "${RC}"
fi

# --- results.md → NOTES/m1w2_results.md ---------------------------------------
echo
echo "==> rendering NOTES/m1w2_results.md"
PYTHONPATH=src "${PY}" scripts/print_report.py "${OUT_DIR}/report.json" \
    > NOTES/m1w2_results.md

# Append the Chapter-4 caption draft (per task §10).
cat >> NOTES/m1w2_results.md <<'EOF'

---

## Caption draft (Chapter 4, Table 4.1)

> **Table 4.1.** Per-competency accuracy of Baseline 1 (no external memory)
> on the LongMemEval-S 50-session development slice. Errors are 95% bootstrap
> CIs over 1,000 resamples. The single-session vs. multi-session gap
> quantifies the value of any cross-session memory mechanism on this benchmark.

EOF

echo "==> NOTES/m1w2_results.md written"
echo
echo "==> M1-W2 finalize complete."
echo "    Next: review NOTES/m1w2_results.md, run §3.4 sanity-check, commit + tag v0.1.1-m1w2-baseline-no-memory."
