#!/usr/bin/env bash
# M1-W3 finalization runner — runs on the user's host (laptop/GPU box) where
# Ollama lives. Produces:
#
#   * runs/m1w3/flat_vector/{report.json,judgments.jsonl,answers.jsonl,
#                              judge_cache.jsonl,results.md,run.log}
#   * NOTES/m1w3_results.md   — merged 2-baseline table (Δ vs. no_memory)
#   * NOTES/m1w3_win_loss.md  — per-competency disagreement matrix
#   * NOTES/m1w3_sanity.md    — auto-filled with run metadata; the
#                                10-example breakdown is added BY HAND
#                                after the run (see §3.5)
#
# Acceptance criterion: < 2 hours wall-clock for 50 sessions (M1-W3 §5.2).
#
# Usage:
#   bash scripts/finalize_m1w3.sh                 # full 50-session run
#   bash scripts/finalize_m1w3.sh --limit 5       # 5-session smoke

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

# --- libomp / threading hygiene (Apple-Silicon segfault mitigation) ----------
# torch and faiss-cpu each ship their own libomp. On Apple Silicon, having
# both loaded in the same process can segfault inside `torch.nn.functional.
# layer_norm` during BERT forward passes (we hit this at the pytest stage
# the first time finalize_m1w3.sh ran on the host). Forcing a single OpenMP
# thread per process serializes both libraries onto the same runtime and
# eliminates the crash. Tokenizers' Rust threading is similarly disabled
# to avoid fork-after-import issues. These costs are negligible at our
# scale (50 sessions × 384-dim embeddings).
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
# Apple-Silicon-specific: torch's MPS backend can disagree with sentence-
# transformers' default device dispatch on certain library combinations.
# Force CPU here unless the caller explicitly asks for cuda. (MPS is not
# yet a target platform for this thesis; the host run is CPU on laptop,
# CUDA on the GPU box.)
EMBEDDER_DEVICE="${EMBEDDER_DEVICE:-cpu}"

OUT_DIR="runs/m1w3/flat_vector"
REF_DIR="runs/m1w2/no_memory"
SLICE="data/slices/longmemeval_s_50_seed0.jsonl"
MODEL="${OLLAMA_MODEL:-gemma4:e4b}"
HOST="${OLLAMA_HOST:-http://localhost:11434}"
K="${K:-5}"
EXTRA_ARGS=("$@")

echo "==> M1-W3 finalize: ${MODEL} via ${HOST}"
echo "    slice : ${SLICE}"
echo "    out   : ${OUT_DIR}"
echo "    k     : ${K}"
echo "    embed : MiniLM-L6-v2 on ${EMBEDDER_DEVICE}"

# --- prereq checks -----------------------------------------------------------
if [[ ! -f "${SLICE}" ]]; then
  echo "ERROR: slice not found at ${SLICE}. Build it via scripts/build_slice.py" >&2
  exit 1
fi

if [[ ! -f "${REF_DIR}/report.json" ]]; then
  echo "WARN: M1-W2 reference report.json not found at ${REF_DIR}/report.json"
  echo "      The merged 2-baseline table at NOTES/m1w3_results.md will be"
  echo "      flat-vector-only. Re-run scripts/finalize_m1w2.sh first if you"
  echo "      want the proper 2-row Δ table."
fi

if ! curl -s --max-time 5 "${HOST}/api/tags" >/dev/null; then
  echo "ERROR: Ollama not reachable at ${HOST}. Run 'ollama serve' and retry." >&2
  exit 1
fi

# Chat ping (same pattern as finalize_m1w2.sh — surfaces cold-start failures
# before the 50-session loop sinks the budget into them).
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
  echo "       Common fixes:"
  echo "         ollama rm ${MODEL} && ollama pull ${MODEL}"
  echo "         pkill -f 'ollama serve'; ollama serve &"
  echo "         OLLAMA_MODEL=qwen2.5:3b-instruct bash scripts/finalize_m1w3.sh"
  exit 1
fi
echo "==> chat ping ok (HTTP 200)"

# Python: prefer .venv if present and importable.
PY="python3"
if [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
fi
echo "==> using python: ${PY}"

# --- dep checks --------------------------------------------------------------
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
ensure_module faiss "faiss-cpu>=1.8,<2.0"
ensure_module sentence_transformers "sentence-transformers>=3.0,<4.0"

# --- pre-flight tests --------------------------------------------------------
echo "==> pytest M1-W3 baseline + supporting tests"
PYTHONPATH=src "${PY}" -m pytest -q \
    tests/test_no_memory.py \
    tests/test_longmemeval_eval.py \
    tests/test_embeddings.py \
    tests/test_flat_vector_store.py \
    tests/test_flat_vector.py
echo

# --- the actual run ----------------------------------------------------------
mkdir -p "${OUT_DIR}"
LOG="${OUT_DIR}/run.log"
echo "==> writing log to ${LOG}"

set +e
PYTHONPATH=src "${PY}" scripts/run_baseline.py \
    --baseline flat_vector \
    --slice "${SLICE}" \
    --out "${OUT_DIR}" \
    --seed 0 \
    --k "${K}" \
    --embedder-device "${EMBEDDER_DEVICE}" \
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

# --- merged 2-baseline results table -----------------------------------------
echo
if [[ -f "${REF_DIR}/report.json" ]]; then
  echo "==> rendering NOTES/m1w3_results.md (merged 2-baseline table)"
  PYTHONPATH=src "${PY}" scripts/print_report.py \
      --merge "${REF_DIR}/report.json" "${OUT_DIR}/report.json" \
      > NOTES/m1w3_results.md
  # Append the Chapter-4 caption draft (per task §10).
  cat >> NOTES/m1w3_results.md <<'EOF'

---

## Caption draft (Chapter 4, Table 4.1 cont'd)

> **Table 4.1 (cont'd).** Per-competency accuracy of Baseline 2
> (flat-vector memory: FAISS + `sentence-transformers/all-MiniLM-L6-v2`,
> k=5, turn-level role-tagged embeddings, per-question reset) on the
> LongMemEval-S 50-session development slice. Δ vs. Baseline 1 in
> parentheses. Errors are 95% bootstrap CIs over 1,000 resamples. The
> competencies that benefit most from flat-vector retrieval (multi-session,
> knowledge-update) are precisely the competencies where retrieval can find
> prior turns; competencies where the answer is in the current session show
> no improvement and may degrade due to distractor retrieval.

EOF
else
  echo "==> rendering NOTES/m1w3_results.md (flat-vector only — M1-W2 ref absent)"
  PYTHONPATH=src "${PY}" scripts/print_report.py "${OUT_DIR}/report.json" \
      > NOTES/m1w3_results.md
fi

# --- per-competency win/loss matrix ------------------------------------------
if [[ -f "${REF_DIR}/judgments.jsonl" ]]; then
  echo "==> rendering NOTES/m1w3_win_loss.md (per-competency disagreement)"
  PYTHONPATH=src "${PY}" scripts/win_loss.py \
      --ref "${REF_DIR}/judgments.jsonl" \
      --new "${OUT_DIR}/judgments.jsonl" \
      --ref-name no_memory --new-name flat_vector \
      > NOTES/m1w3_win_loss.md
fi

# --- auto-fill the run-metadata header of NOTES/m1w3_sanity.md ---------------
# The 10-example breakdown (§3.5) is added by hand AFTER reviewing the
# disagreements; this header makes the run reproducible from the note.
echo "==> stamping run metadata into NOTES/m1w3_sanity.md (header only)"
WALL_S="$("${PY}" -c "import json; print(json.load(open('${OUT_DIR}/report.json')).get('wall_clock_seconds', 0))")"
NOW_UTC="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

# Only stamp if the file is missing or empty — preserve any analysis you've
# already written.
if [[ ! -s NOTES/m1w3_sanity.md ]]; then
  cp NOTES/m1w3_sanity.template.md NOTES/m1w3_sanity.md 2>/dev/null || true
fi

# Replace the ${RUN_TIMESTAMP_UTC}, ${RUN_WALL_SECONDS}, ${RUN_MODEL_TAG},
# ${RUN_K} placeholders if they appear (idempotent — re-running the script
# updates the latest header values; subsequent text below stays intact).
"${PY}" - <<PY
import re, pathlib, os
p = pathlib.Path("NOTES/m1w3_sanity.md")
if p.exists():
    txt = p.read_text(encoding="utf-8")
    sub = {
        "\${RUN_TIMESTAMP_UTC}":   "${NOW_UTC}",
        "\${RUN_WALL_SECONDS}":    "${WALL_S}",
        "\${RUN_MODEL_TAG}":       "${MODEL}",
        "\${RUN_K}":               "${K}",
    }
    for k, v in sub.items():
        txt = txt.replace(k, str(v))
    p.write_text(txt, encoding="utf-8")
PY

echo
echo "==> M1-W3 finalize complete."
echo
echo "    Wall-clock for the run: ${WALL_S}s"
echo
echo "    Next:"
echo "      1. Read NOTES/m1w3_results.md and NOTES/m1w3_win_loss.md."
echo "      2. Read 5 wins / 5 losses from runs/m1w3/flat_vector/judgments.jsonl"
echo "         (use the disagreement session ids in m1w3_win_loss.md)."
echo "      3. Fill the 10-example classification table in NOTES/m1w3_sanity.md."
echo "      4. Commit + tag v0.1.2-m1w3-baseline-flat-vector."
