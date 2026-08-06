#!/usr/bin/env bash
# Run a contiguous LongMemEval-M range against OpenAI-compatible endpoints.
#
# Example:
#   bash deploy/setup_colab_modal_range.sh
#
#   SAMPLE_FROM=0 SAMPLE_TO=49 bash deploy/run_colab_modal_range.sh
#
# Range semantics:
#   SAMPLE_FROM / SAMPLE_TO are zero-based and inclusive.
#   SAMPLE_FROM=0 SAMPLE_TO=49 evaluates the first 50 samples.
set -euo pipefail

cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
export PYTHONPATH="src:${PYTHONPATH:-}"

# Python's urllib reads the macOS system proxy configuration even when the
# shell has no proxy variables.  Keep every local embed request on loopback;
# otherwise a configured Privoxy can return HTTP 500 for 127.0.0.1.
_LOOPBACK_NO_PROXY="127.0.0.1,localhost,::1"
export NO_PROXY="${NO_PROXY:+${NO_PROXY},}${_LOOPBACK_NO_PROXY}"
export no_proxy="${no_proxy:+${no_proxy},}${_LOOPBACK_NO_PROXY}"

PYTHON="${PYTHON:-python3}"
MODAL_KEY="${MODAL_KEY:-}"
MODAL_SECRET="${MODAL_SECRET:-}"
if [[ -n "${MODAL_KEY}" || -n "${MODAL_SECRET}" ]]; then
  export MODAL_KEY MODAL_SECRET
fi
DATASET="${DATASET:-m}"
SRC="${SRC:-data/longmemeval_${DATASET}_cleaned.json}"
SLICE="${SLICE:-data/slices/longmemeval_${DATASET}_full.jsonl}"
RANGE_SLICE_OVERRIDE="${RANGE_SLICE_OVERRIDE:-}"
OUT="${OUT:-runs/lme_${DATASET}_modal_range_seed${SEED:-0}}"
SYSTEMS="${SYSTEMS:-controller}"
SHARDS="${SHARDS:-10}"
SEED="${SEED:-0}"
SAMPLE_FROM="${SAMPLE_FROM:-1}"
SAMPLE_TO="${SAMPLE_TO:-50}"
EMBED_PORT="${EMBED_PORT:-8100}"
EMBED_BASE_URL="${EMBED_BASE_URL:-http://127.0.0.1:${EMBED_PORT}/v1}"
START_EMBED_SERVER="${START_EMBED_SERVER:-1}"
EMBED_MODEL_PATH="${EMBED_MODEL_PATH:-jinaai/jina-embeddings-v5-text-nano}"
EMBED_MODEL_NAME="${EMBED_MODEL_NAME:-jina}"
EMBED_TASK="${EMBED_TASK:-retrieval}"
EMBED_TRUST_REMOTE_CODE="${EMBED_TRUST_REMOTE_CODE:-1}"
EMBED_DEVICE="${EMBED_DEVICE:-mps}"
EMBED_BATCH_SIZE="${EMBED_BATCH_SIZE:-4}"
EMBED_CLIENT_BATCH_SIZE="${EMBED_CLIENT_BATCH_SIZE:-4}"
EMBED_MAX_SEQ_LENGTH="${EMBED_MAX_SEQ_LENGTH:-256}"
EMBED_READY_TIMEOUT_S="${EMBED_READY_TIMEOUT_S:-240}"
OPENROUTER_BASE_URL="${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}"
FAST_BASE_URL="${FAST_BASE_URL:-${OPENROUTER_BASE_URL}}"
FAST_MODEL="${FAST_MODEL:-qwen/qwen3.5-9b}"
BIG_BASE_URL="${BIG_BASE_URL:-${OPENROUTER_BASE_URL}}"
BIG_MODEL="${BIG_MODEL:-qwen/qwen3.5-9b}"
ANSWER_ESCALATION_BASE_URL="${ANSWER_ESCALATION_BASE_URL:-${BIG_BASE_URL}}"
ANSWER_ESCALATION_MODEL="${ANSWER_ESCALATION_MODEL:-}"
JUDGE_MODEL="${JUDGE_MODEL:-google/gemma-4-31b-it}"
JUDGE_OPENAI_BASE_URL="${JUDGE_OPENAI_BASE_URL:-}"
JUDGE_OPENAI_API_KEY_ENV="${JUDGE_OPENAI_API_KEY_ENV:-}"
OPENAI_API_KEY_ENV="${OPENAI_API_KEY_ENV:-OPENROUTER_API_KEY}"
OPENAI_TIMEOUT_S="${OPENAI_TIMEOUT_S:-300}"
OPENAI_RETRY_MAX_ATTEMPTS="${OPENAI_RETRY_MAX_ATTEMPTS:-3}"
OPENAI_RETRY_INITIAL_DELAY_S="${OPENAI_RETRY_INITIAL_DELAY_S:-1}"
OPENAI_RETRY_MAX_DELAY_S="${OPENAI_RETRY_MAX_DELAY_S:-10}"
# Output token budgets for the structured-JSON stages. The previous cascade
# defaults (256/128) truncated ~7% of extraction/relation calls mid-JSON
# (finish_reason=length -> "Unterminated string"), silently dropping memory
# facts. Raise them so the JSON objects complete.
EXTRACTION_MAX_NEW_TOKENS="${EXTRACTION_MAX_NEW_TOKENS:-512}"
RELATION_MAX_NEW_TOKENS="${RELATION_MAX_NEW_TOKENS:-256}"
# Answerer context window for the controller prompt-budgeter. At 8192 the
# controller discarded ~70% of retrieved memory (items 214->50) before the
# model saw it -> false "Unknown" answers. At 16384 the v5 run still trimmed
# 320->134 items. qwen3.5-9b supports 32k+ on the routed providers, so default
# to 32768 (v4 ran it without issue).
OPENAI_MAX_MODEL_LEN="${OPENAI_MAX_MODEL_LEN:-32768}"
ANSWER_MODEL="${ANSWER_MODEL:-}"
ANSWER_MAX_NEW_TOKENS="${ANSWER_MAX_NEW_TOKENS:-768}"
ANSWER_OPENAI_EXTRA_BODY_JSON="${ANSWER_OPENAI_EXTRA_BODY_JSON:-}"
# --- docx v7 knobs (§4 accuracy + §5 efficiency). Defaults apply the fixes. ---
RETRIEVAL_K="${RETRIEVAL_K:-16}"
CONTROLLER_MEMORY_TOP_K="${CONTROLLER_MEMORY_TOP_K:-64}"
EXTRACTION_CONCURRENCY="${EXTRACTION_CONCURRENCY:-8}"
ANSWER_CONTEXT_MAX_TOKENS="${ANSWER_CONTEXT_MAX_TOKENS:-12000}"
V7_FIXES="${V7_FIXES:-1}"
V8_FIXES="${V8_FIXES:-1}"
V9_FIXES="${V9_FIXES:-1}"
HISTORY_RETRIEVAL_K="${HISTORY_RETRIEVAL_K:-4}"
ANSWER_CONTEXT_SESSION_CAP="${ANSWER_CONTEXT_SESSION_CAP:-4}"
COMPETENCY_USER_CANDIDATE_K="${COMPETENCY_USER_CANDIDATE_K:-120}"
COMPETENCY_ASSISTANT_CANDIDATE_K="${COMPETENCY_ASSISTANT_CANDIDATE_K:-60}"
COMPETENCY_SESSION_TOP_K="${COMPETENCY_SESSION_TOP_K:-12}"
COMPETENCY_PREFERENCE_SESSION_TOP_K="${COMPETENCY_PREFERENCE_SESSION_TOP_K:-18}"
SHARD_RETRIES="${SHARD_RETRIES:-2}"
SHARD_RETRY_BACKOFF_S="${SHARD_RETRY_BACKOFF_S:-5}"
SHARED_EXTRACTION_CACHE="${SHARED_EXTRACTION_CACHE:-}"
OPENAI_CHAT_TEMPLATE_KWARGS_JSON="${OPENAI_CHAT_TEMPLATE_KWARGS_JSON:-}"
# Hold JSON defaults in plain single-quoted vars. Bash `${VAR:-word}` ends the
# default at the FIRST `}` in `word`, so inline JSON braces don't nest: any
# trailing `}` become literal text appended after the expansion and silently
# corrupt a user override (e.g. a valid `...true}}` came out as `...true}}}}`).
# "reasoning":{"enabled":false} is REQUIRED for qwen3.5 via OpenRouter: with
# provider reasoning on, the model burns the entire completion budget in the
# invisible thinking channel and returns 0 visible chars (v5 run: every answer
# empty with finish_reason=length, every extraction itemless). The controller's
# own WORK/FINAL prompt supplies visible, parseable reasoning instead.
# No provider.order here: OpenRouter's default policy load-balances concurrent
# requests across this constrained pool and falls back when a route is limited.
_DEFAULT_OPENAI_EXTRA_BODY_JSON='{"provider":{"only":["venice","deepinfra","siliconflow"],"allow_fallbacks":true},"reasoning":{"enabled":false}}'
OPENAI_EXTRA_BODY_JSON="${OPENAI_EXTRA_BODY_JSON:-${_DEFAULT_OPENAI_EXTRA_BODY_JSON}}"
JUDGE_OPENAI_CHAT_TEMPLATE_KWARGS_JSON="${JUDGE_OPENAI_CHAT_TEMPLATE_KWARGS_JSON:-}"
_DEFAULT_JUDGE_OPENAI_EXTRA_BODY_JSON='{"provider":{"order":["wandb","venice"],"only":["wandb","venice"],"allow_fallbacks":true},"reasoning":{"enabled":false}}'
JUDGE_OPENAI_EXTRA_BODY_JSON="${JUDGE_OPENAI_EXTRA_BODY_JSON:-${_DEFAULT_JUDGE_OPENAI_EXTRA_BODY_JSON}}"
JUDGE_OPENAI_FALLBACK_MODEL="${JUDGE_OPENAI_FALLBACK_MODEL:-}"
OPENMODEL_PRIMARY="${OPENMODEL_PRIMARY:-0}"
OPENMODEL_BASE_URL="${OPENMODEL_BASE_URL:-https://api.openmodel.ai/v1}"
OPENMODEL_MODEL="${OPENMODEL_MODEL:-}"
OPENMODEL_API_KEY_ENV="${OPENMODEL_API_KEY_ENV:-OPENMODEL_API_KEY}"
OPENMODEL_API_KEY_ENVS="${OPENMODEL_API_KEY_ENVS:-OPENMODEL_KEY1,OPENMODEL_KEY2,OPENMODEL_KEY3,OPENMODEL_KEY4,OPENMODEL_KEY5,OPENMODEL_KEY6,OPENMODEL_KEY7}"
OPENMODEL_TIMEOUT_S="${OPENMODEL_TIMEOUT_S:-120}"
LOG_DIR="${LOG_DIR:-${OUT}/logs}"
MAIN_LOG="${MAIN_LOG:-${LOG_DIR}/main.log}"
EMBED_LOG="${EMBED_LOG:-${LOG_DIR}/embed_server.log}"

mkdir -p "${LOG_DIR}"
exec > >(tee -a "${MAIN_LOG}") 2>&1

# Fail fast on malformed JSON env vars instead of crashing deep in a subprocess.
_validate_json() {
  local label="$1" value="$2"
  [[ -z "${value}" ]] && return 0
  if ! printf '%s' "${value}" | "${PYTHON}" -c 'import json,sys; json.loads(sys.stdin.read())' 2>/dev/null; then
    echo "[colab-modal] ERROR: ${label} is not valid JSON:" >&2
    echo "  ${value}" >&2
    exit 2
  fi
}
_validate_json "OPENAI_EXTRA_BODY_JSON" "${OPENAI_EXTRA_BODY_JSON}"
_validate_json "JUDGE_OPENAI_EXTRA_BODY_JSON" "${JUDGE_OPENAI_EXTRA_BODY_JSON}"
_validate_json "OPENAI_CHAT_TEMPLATE_KWARGS_JSON" "${OPENAI_CHAT_TEMPLATE_KWARGS_JSON}"
_validate_json "JUDGE_OPENAI_CHAT_TEMPLATE_KWARGS_JSON" "${JUDGE_OPENAI_CHAT_TEMPLATE_KWARGS_JSON}"

case "${OPENAI_API_KEY_ENV}" in
  [sS][kK]-*|[sS][kK]_* )
  echo "[colab-modal] ERROR: OPENAI_API_KEY_ENV must be an environment variable name, not the key value." >&2
  echo "[colab-modal] Example: OPENROUTER_API_KEY=<secret> OPENAI_API_KEY_ENV=OPENROUTER_API_KEY bash deploy/run_colab_modal_range.sh" >&2
  exit 2
  ;;
esac

echo "[colab-modal] command:"
echo "  SAMPLE_FROM=${SAMPLE_FROM} SAMPLE_TO=${SAMPLE_TO} \\"
echo "  SYSTEMS=${SYSTEMS} \\"
echo "  SHARDS=${SHARDS} \\"
echo "  bash deploy/run_colab_modal_range.sh"
echo "[colab-modal] config:"
echo "  dataset=${DATASET}"
echo "  slice=${SLICE}"
echo "  range_slice_override=${RANGE_SLICE_OVERRIDE:-<materialize from slice>}"
echo "  out=${OUT}"
echo "  logs=${LOG_DIR}"
echo "  main_log=${MAIN_LOG}"
echo "  embed_log=${EMBED_LOG}"
echo "  embed_base_url=${EMBED_BASE_URL}"
echo "  start_embed_server=${START_EMBED_SERVER}"
echo "  embed_model_path=${EMBED_MODEL_PATH}"
echo "  embed_model_name=${EMBED_MODEL_NAME}"
echo "  embed_task=${EMBED_TASK:-<none>}"
echo "  embed_device=${EMBED_DEVICE}"
echo "  embed_batch_size=${EMBED_BATCH_SIZE}"
echo "  embed_client_batch_size=${EMBED_CLIENT_BATCH_SIZE}"
echo "  embed_max_seq_length=${EMBED_MAX_SEQ_LENGTH}"
echo "  embed_ready_timeout_s=${EMBED_READY_TIMEOUT_S}"
echo "  fast_base_url=${FAST_BASE_URL:-<default>}"
echo "  fast_model=${FAST_MODEL:-<default>}"
echo "  big_base_url=${BIG_BASE_URL:-<default>}"
echo "  big_model=${BIG_MODEL:-<default>}"
echo "  answer_escalation_base_url=${ANSWER_ESCALATION_BASE_URL:-<default>}"
echo "  answer_escalation_model=${ANSWER_ESCALATION_MODEL:-<disabled>}"
echo "  judge_model=${JUDGE_MODEL:-<default>}"
echo "  judge_openai_base_url=${JUDGE_OPENAI_BASE_URL:-<none>}"
echo "  judge_openai_api_key_env=${JUDGE_OPENAI_API_KEY_ENV:-<none>}"
echo "  openai_api_key_env=${OPENAI_API_KEY_ENV}"
echo "  openai_timeout_s=${OPENAI_TIMEOUT_S}"
echo "  openai_retry_max_attempts=${OPENAI_RETRY_MAX_ATTEMPTS}"
echo "  openai_retry_initial_delay_s=${OPENAI_RETRY_INITIAL_DELAY_S}"
echo "  openai_retry_max_delay_s=${OPENAI_RETRY_MAX_DELAY_S}"
echo "  extraction_max_new_tokens=${EXTRACTION_MAX_NEW_TOKENS}"
echo "  relation_max_new_tokens=${RELATION_MAX_NEW_TOKENS}"
echo "  openai_max_model_len=${OPENAI_MAX_MODEL_LEN}"
echo "  answer_model=${ANSWER_MODEL:-<big-model default>}"
echo "  answer_max_new_tokens=${ANSWER_MAX_NEW_TOKENS}"
echo "  answer_openai_extra_body_json=${ANSWER_OPENAI_EXTRA_BODY_JSON:-<global default>}"
echo "  retrieval_k=${RETRIEVAL_K}"
echo "  controller_memory_top_k=${CONTROLLER_MEMORY_TOP_K}"
echo "  extraction_concurrency=${EXTRACTION_CONCURRENCY}"
echo "  answer_context_max_tokens=${ANSWER_CONTEXT_MAX_TOKENS}"
echo "  v7_fixes=${V7_FIXES}"
echo "  v8_fixes=${V8_FIXES}"
echo "  v9_fixes=${V9_FIXES}"
echo "  history_retrieval_k=${HISTORY_RETRIEVAL_K}"
echo "  answer_context_session_cap=${ANSWER_CONTEXT_SESSION_CAP}"
echo "  competency_user_candidate_k=${COMPETENCY_USER_CANDIDATE_K}"
echo "  competency_assistant_candidate_k=${COMPETENCY_ASSISTANT_CANDIDATE_K}"
echo "  competency_session_top_k=${COMPETENCY_SESSION_TOP_K}"
echo "  competency_preference_session_top_k=${COMPETENCY_PREFERENCE_SESSION_TOP_K}"
echo "  shard_retries=${SHARD_RETRIES}"
echo "  shard_retry_backoff_s=${SHARD_RETRY_BACKOFF_S}"
echo "  shared_extraction_cache=${SHARED_EXTRACTION_CACHE:-<per-run default>}"
echo "  openai_extra_body_json=${OPENAI_EXTRA_BODY_JSON}"
echo "  judge_openai_extra_body_json=${JUDGE_OPENAI_EXTRA_BODY_JSON}"
echo "  judge_openai_fallback_model=${JUDGE_OPENAI_FALLBACK_MODEL:-<none>}"
echo "  openmodel_primary=${OPENMODEL_PRIMARY}"
echo "  openmodel_base_url=${OPENMODEL_BASE_URL}"
echo "  openmodel_model=${OPENMODEL_MODEL:-<mapped>}"
echo "  openmodel_api_key_env=${OPENMODEL_API_KEY_ENV}"
echo "  openmodel_api_key_envs=${OPENMODEL_API_KEY_ENVS}"

if [[ -z "${FAST_BASE_URL}" || -z "${BIG_BASE_URL}" ]]; then
  echo "[colab-modal] ERROR: FAST_BASE_URL and BIG_BASE_URL must be set" >&2
  exit 2
fi

if [[ ! -f "${SRC}" ]]; then
  echo "[colab-modal] ERROR: missing ${SRC}" >&2
  echo "[colab-modal] Run setup first: bash deploy/setup_colab_modal_range.sh" >&2
  exit 2
fi

if [[ ! -f "${SLICE}" ]]; then
  echo "[colab-modal] ERROR: missing ${SLICE}" >&2
  echo "[colab-modal] Run setup first: bash deploy/setup_colab_modal_range.sh" >&2
  exit 2
fi

if [[ "${START_EMBED_SERVER}" == "1" ]]; then
  if [[ "${EMBED_DEVICE}" == cuda* ]]; then
    "${PYTHON}" - <<'PY'
import torch
print(f"[colab-modal] torch={torch.__version__} cuda={torch.version.cuda} available={torch.cuda.is_available()}")
if not torch.cuda.is_available():
    raise SystemExit("[colab-modal] ERROR: torch CUDA is unavailable; run setup on a GPU runtime.")
print(f"[colab-modal] gpu={torch.cuda.get_device_name(0)}")
PY
  fi
  echo "[colab-modal] starting embed server on ${EMBED_BASE_URL}"
  embed_cmd=(
    "${PYTHON}" scripts/serve_embeddings.py
    --model "${EMBED_MODEL_PATH}"
    --served-name "${EMBED_MODEL_NAME}"
    --device "${EMBED_DEVICE}"
    --batch-size "${EMBED_BATCH_SIZE}"
    --max-seq-length "${EMBED_MAX_SEQ_LENGTH}"
    --host 127.0.0.1
    --port "${EMBED_PORT}"
  )
  if [[ -n "${EMBED_TASK}" ]]; then
    embed_cmd+=(--task "${EMBED_TASK}")
  fi
  if [[ "${EMBED_TRUST_REMOTE_CODE}" == "1" ]]; then
    embed_cmd+=(--trust-remote-code)
  fi
  printf '[colab-modal] embed command:' > "${EMBED_LOG}"
  printf ' %q' "${embed_cmd[@]}" >> "${EMBED_LOG}"
  printf '\n\n' >> "${EMBED_LOG}"
  "${embed_cmd[@]}" >> "${EMBED_LOG}" 2>&1 &
  EMBED_PID="$!"
  cleanup() {
    kill "${EMBED_PID}" >/dev/null 2>&1 || true
  }
  trap cleanup EXIT
fi

echo "[colab-modal] waiting for embed server health: ${EMBED_BASE_URL}"
"${PYTHON}" - <<PY
import json
import time
import urllib.error
import urllib.parse
import urllib.request

base = "${EMBED_BASE_URL}".rstrip("/")
parsed = urllib.parse.urlparse(base)
path = parsed.path.removesuffix("/v1")
url = urllib.parse.urlunparse(parsed._replace(path=f"{path}/health"))
open_url = urllib.request.urlopen
if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
    open_url = urllib.request.build_opener(urllib.request.ProxyHandler({})).open
deadline = time.time() + int("${EMBED_READY_TIMEOUT_S}")
last_error = None
while time.time() < deadline:
    try:
        with open_url(url, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("status") == "ok" or payload.get("ok") is True:
            print(f"[colab-modal] embed health ok: {json.dumps(payload, sort_keys=True)}")
            raise SystemExit(0)
        last_error = f"unexpected health payload: {payload}"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        last_error = f"{type(exc).__name__}: {exc}"
    time.sleep(2)
raise SystemExit(f"[colab-modal] embed server did not become healthy: {last_error}")
PY

mkdir -p "${OUT}"
echo "[colab-modal] starting cascade:"
echo "  systems=${SYSTEMS}"
echo "  sample=${SAMPLE_FROM}-${SAMPLE_TO}"
RANGE_SLICE="${OUT}/range_${SAMPLE_FROM}_${SAMPLE_TO}.jsonl"
if [[ -n "${RANGE_SLICE_OVERRIDE}" ]]; then
  RANGE_SLICE="${RANGE_SLICE_OVERRIDE}"
  if [[ ! -f "${RANGE_SLICE}" ]]; then
    echo "[colab-modal] ERROR: missing RANGE_SLICE_OVERRIDE=${RANGE_SLICE}" >&2
    exit 2
  fi
  "${PYTHON}" - <<PY
from pathlib import Path

path = Path("${RANGE_SLICE}")
actual = sum(1 for line in path.open(encoding="utf-8") if line.strip())
expected = int("${SAMPLE_TO}") - int("${SAMPLE_FROM}") + 1
if actual != expected:
    raise SystemExit(
        f"RANGE_SLICE_OVERRIDE has {actual} rows; expected {expected} "
        f"for range ${SAMPLE_FROM}-${SAMPLE_TO}"
    )
print(f"[colab-modal] reusing pre-sliced input: {path} rows={actual}")
PY
else
  "${PYTHON}" - <<PY
from pathlib import Path

src = Path("${SLICE}")
dst = Path("${RANGE_SLICE}")
start = int("${SAMPLE_FROM}")
end = int("${SAMPLE_TO}")

if start < 0:
    raise SystemExit("SAMPLE_FROM must be >= 0")
if end < start:
    raise SystemExit("SAMPLE_TO must be >= SAMPLE_FROM")

dst.parent.mkdir(parents=True, exist_ok=True)
n = 0
with src.open("r", encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
    for i, line in enumerate(fin):
        if i < start:
            continue
        if i > end:
            break
        fout.write(line)
        n += 1

if n == 0:
    raise SystemExit(f"empty range: {start}-{end} from {src}")
print(f"[colab-modal] wrote range slice: {dst} rows={n}")
PY
fi
echo "  range_slice=${RANGE_SLICE}"
echo "  shards=${SHARDS}"
echo "  per-shard logs=${LOG_DIR}/{system}_shard{n}.log"
cascade_cmd=(
  "${PYTHON}" scripts/run_vllm_cascade.py
  --slice "${RANGE_SLICE}" \
  --out "${OUT}" \
  --log-dir "${LOG_DIR}" \
  --systems "${SYSTEMS}" \
  --shards "${SHARDS}" \
  --shard-retries "${SHARD_RETRIES}" \
  --shard-retry-backoff-s "${SHARD_RETRY_BACKOFF_S}" \
  --openai-api-key-env "${OPENAI_API_KEY_ENV}" \
  --openai-timeout-s "${OPENAI_TIMEOUT_S}" \
  --openai-retry-max-attempts "${OPENAI_RETRY_MAX_ATTEMPTS}" \
  --openai-retry-initial-delay-s "${OPENAI_RETRY_INITIAL_DELAY_S}" \
  --openai-retry-max-delay-s "${OPENAI_RETRY_MAX_DELAY_S}" \
  --embed-base-url "${EMBED_BASE_URL}" \
  --embed-model "${EMBED_MODEL_NAME}" \
  --embed-batch-size "${EMBED_CLIENT_BATCH_SIZE}" \
  --extraction-max-new-tokens "${EXTRACTION_MAX_NEW_TOKENS}" \
  --relation-max-new-tokens "${RELATION_MAX_NEW_TOKENS}" \
  --openai-max-model-len "${OPENAI_MAX_MODEL_LEN}" \
  --answer-max-new-tokens "${ANSWER_MAX_NEW_TOKENS}" \
  --retrieval-k "${RETRIEVAL_K}" \
  --controller-memory-top-k "${CONTROLLER_MEMORY_TOP_K}" \
  --extraction-concurrency "${EXTRACTION_CONCURRENCY}" \
  --answer-context-max-tokens "${ANSWER_CONTEXT_MAX_TOKENS}" \
  --history-retrieval-k "${HISTORY_RETRIEVAL_K}" \
  --answer-context-session-cap "${ANSWER_CONTEXT_SESSION_CAP}" \
  --competency-user-candidate-k "${COMPETENCY_USER_CANDIDATE_K}" \
  --competency-assistant-candidate-k "${COMPETENCY_ASSISTANT_CANDIDATE_K}" \
  --competency-session-top-k "${COMPETENCY_SESSION_TOP_K}" \
  --competency-preference-session-top-k "${COMPETENCY_PREFERENCE_SESSION_TOP_K}"
)
if [[ -n "${ANSWER_MODEL}" ]]; then
  cascade_cmd+=(--answer-model "${ANSWER_MODEL}")
fi
if [[ -n "${ANSWER_OPENAI_EXTRA_BODY_JSON}" ]]; then
  cascade_cmd+=(--answer-openai-extra-body-json "${ANSWER_OPENAI_EXTRA_BODY_JSON}")
fi
# docx v7 accuracy fixes: on by default; set V7_FIXES=0 to reproduce v6 behavior.
if [[ "${V7_FIXES}" == "0" ]]; then
  cascade_cmd+=(--no-v7-fixes)
else
  cascade_cmd+=(--v7-fixes)
fi
# v8 controller fixes are an overlay; disable to reproduce the v7 path.
if [[ "${V8_FIXES}" == "0" ]]; then
  cascade_cmd+=(--no-v8-fixes)
else
  cascade_cmd+=(--v8-fixes)
fi
# v9 adds competency-aware retrieval and deterministic reconciliation.
if [[ "${V9_FIXES}" == "0" ]]; then
  cascade_cmd+=(--no-v9-fixes)
else
  cascade_cmd+=(--v9-fixes)
fi
if [[ -n "${SHARED_EXTRACTION_CACHE}" ]]; then
  cascade_cmd+=(--shared-extraction-cache "${SHARED_EXTRACTION_CACHE}")
fi
if [[ -n "${FAST_BASE_URL}" ]]; then
  cascade_cmd+=(--fast-base-url "${FAST_BASE_URL}")
fi
if [[ -n "${FAST_MODEL}" ]]; then
  cascade_cmd+=(--fast-model "${FAST_MODEL}")
fi
if [[ -n "${BIG_BASE_URL}" ]]; then
  cascade_cmd+=(--big-base-url "${BIG_BASE_URL}")
fi
if [[ -n "${BIG_MODEL}" ]]; then
  cascade_cmd+=(--big-model "${BIG_MODEL}")
fi
if [[ -n "${ANSWER_ESCALATION_MODEL}" ]]; then
  cascade_cmd+=(
    --answer-escalation-base-url "${ANSWER_ESCALATION_BASE_URL}"
    --answer-escalation-model "${ANSWER_ESCALATION_MODEL}"
  )
fi
if [[ -n "${JUDGE_MODEL}" ]]; then
  cascade_cmd+=(--judge-model "${JUDGE_MODEL}")
fi
if [[ -n "${OPENAI_CHAT_TEMPLATE_KWARGS_JSON}" ]]; then
  cascade_cmd+=(--openai-chat-template-kwargs-json "${OPENAI_CHAT_TEMPLATE_KWARGS_JSON}")
fi
if [[ -n "${OPENAI_EXTRA_BODY_JSON}" ]]; then
  cascade_cmd+=(--openai-extra-body-json "${OPENAI_EXTRA_BODY_JSON}")
fi
if [[ "${OPENMODEL_PRIMARY}" == "1" ]]; then
  cascade_cmd+=(
    --openmodel-primary
    --openmodel-base-url "${OPENMODEL_BASE_URL}"
    --openmodel-api-key-env "${OPENMODEL_API_KEY_ENV}"
    --openmodel-api-key-envs "${OPENMODEL_API_KEY_ENVS}"
    --openmodel-timeout-s "${OPENMODEL_TIMEOUT_S}"
  )
  if [[ -n "${OPENMODEL_MODEL}" ]]; then
    cascade_cmd+=(--openmodel-model "${OPENMODEL_MODEL}")
  fi
fi
if [[ -n "${JUDGE_OPENAI_CHAT_TEMPLATE_KWARGS_JSON}" ]]; then
  cascade_cmd+=(--judge-openai-chat-template-kwargs-json "${JUDGE_OPENAI_CHAT_TEMPLATE_KWARGS_JSON}")
fi
if [[ -n "${JUDGE_OPENAI_EXTRA_BODY_JSON}" ]]; then
  cascade_cmd+=(--judge-openai-extra-body-json "${JUDGE_OPENAI_EXTRA_BODY_JSON}")
fi
if [[ -n "${JUDGE_OPENAI_FALLBACK_MODEL}" ]]; then
  IFS=',' read -r -a _judge_fallback_models <<< "${JUDGE_OPENAI_FALLBACK_MODEL}"
  for _model in "${_judge_fallback_models[@]}"; do
    _model="${_model#"${_model%%[![:space:]]*}"}"
    _model="${_model%"${_model##*[![:space:]]}"}"
    [[ -n "${_model}" ]] && cascade_cmd+=(--judge-openai-fallback-model "${_model}")
  done
fi
if [[ -n "${JUDGE_OPENAI_BASE_URL}" ]]; then
  cascade_cmd+=(--judge-openai-base-url "${JUDGE_OPENAI_BASE_URL}")
fi
if [[ -n "${JUDGE_OPENAI_API_KEY_ENV}" ]]; then
  cascade_cmd+=(--judge-openai-api-key-env "${JUDGE_OPENAI_API_KEY_ENV}")
fi
"${cascade_cmd[@]}"
