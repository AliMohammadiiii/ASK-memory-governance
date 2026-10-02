#!/usr/bin/env bash
# FROZEN homogeneous LongMemEval-M rerun on the same 180-question stratified
# slice, one configuration, one judge policy, no failure-replay patching, and no
# adjudication baked into the numbers. The default runs all five systems
# (controller, b4, b3, b2, b1); --controller-only runs the contribution alone
# through the identical frozen path. This is the only path to a final-candidate
# LongMemEval result; the v7 diagnostic and contradicted 77.2% failure-replay
# construction are not prior final results.
#
# Config is pinned to configs/release/final.yaml. Underlying real entry points:
#   deploy/run_colab_modal_range.sh -> scripts/run_vllm_cascade.py
#   (+ scripts/serve_embeddings.py for the local MiniLM embed server).
#
# This wrapper pins one paid judge route for every item. The V9 free-primary
# policy generated heavy HTTP 429 traffic and silently split most judgments
# across a fallback model, so V12 has no model fallback: a transport failure is
# retried and then fails the shard instead of changing the evaluator. V12 also
# bypasses macOS system proxies for the local MiniLM health/client requests.
#
# HARD PREREQUISITES (the script refuses to run without them):
#   1. OPENROUTER_API_KEY  -- a valid OpenRouter API key.
#   2. LONGMEMEVAL_DATA     -- path to the LongMemEval-M full slice jsonl
#                              (external data; not redistributed in this repo).
#      Optionally LONGMEMEVAL_SRC -> the cleaned source json
#      (default data/longmemeval_m_cleaned.json), required by the underlying
#      range runner's existence check.
#
# Usage:
#   OPENROUTER_API_KEY=sk-or-... LONGMEMEVAL_DATA=/path/longmemeval_m_full.jsonl \
#     bash scripts/evaluation/run_longmemeval_final.sh --full
#   ... --full --controller-only  # same frozen path, controller only
#   ... --smoke     # 2-item end-to-end sanity (hits the API; tiny)
#   ... --resume    # continue an interrupted --full run in place
#   ... --dry-run   # print the exact underlying command, run nothing
#
# macOS-compatible; python3 only.
set -euo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
cd "$REPO"

if [ -z "${PYTHON:-}" ]; then
  if [ -x .venv/bin/python ]; then PYTHON=".venv/bin/python"; else PYTHON="python3"; fi
fi

MODE="--full"
RESUME=0
DRY=0
SYSTEMS="controller,b4,b3,b2,b1"
RUN_SCOPE="all-systems"
for arg in "$@"; do
  case "$arg" in
    --full) MODE="--full" ;;
    --smoke) MODE="--smoke" ;;
    --controller-only) SYSTEMS="controller"; RUN_SCOPE="controller-only" ;;
    --all-systems) SYSTEMS="controller,b4,b3,b2,b1"; RUN_SCOPE="all-systems" ;;
    --resume) RESUME=1 ;;
    --dry-run) DRY=1 ;;
    *) echo "[lme-final] unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# --- frozen models / judge / embedder ---------------------------------- #
MAIN_MODEL="qwen/qwen3.5-9b"
ANSWER_MODEL="$MAIN_MODEL"
JUDGE_PRIMARY="google/gemma-4-31b-it"
JUDGE_FALLBACK=""
# Final answers and answer-contract retries stay on the evaluated Qwen model.
# Keeping the roles explicit preserves provenance without substituting models.
ANSWER_ESCALATION="$ANSWER_MODEL"
EMBED_ST="sentence-transformers/all-MiniLM-L6-v2"
SEED=0
ACCURACY_THRESHOLD="0.85"
ACCURACY_REQUIRED_CORRECT=153
MEMORY_PROVIDER_SLUGS="venice,deepinfra,siliconflow"
MEMORY_PROVIDER_POLICY_JSON='{"provider":{"only":["venice","deepinfra","siliconflow"],"allow_fallbacks":true},"reasoning":{"enabled":false}}'
ANSWER_PROVIDER_POLICY_JSON='{"provider":{"only":["venice","deepinfra","siliconflow"],"allow_fallbacks":true},"reasoning":{"enabled":false}}'

echo "[lme-final] ===== FROZEN CONFIG (configs/release/final.yaml) ====="
echo "[lme-final] memory model     : $MAIN_MODEL (extractor/relation)"
echo "[lme-final] answer model     : $ANSWER_MODEL (reasoning disabled)"
echo "[lme-final] judge primary     : $JUDGE_PRIMARY"
echo "[lme-final] judge fallback     : ${JUDGE_FALLBACK:-<disabled>}"
echo "[lme-final] answer escalation  : $ANSWER_ESCALATION"
echo "[lme-final] memory providers   : $MEMORY_PROVIDER_SLUGS (OpenRouter load-balanced)"
echo "[lme-final] answer providers   : $MEMORY_PROVIDER_SLUGS (OpenRouter load-balanced)"
echo "[lme-final] embedder           : $EMBED_ST (MiniLM-L6-v2, cpu)"
echo "[lme-final] seed               : $SEED"
echo "[lme-final] controller target  : >=${ACCURACY_REQUIRED_CORRECT}/180 (${ACCURACY_THRESHOLD})"
echo "[lme-final] systems            : $SYSTEMS ($RUN_SCOPE)"
echo "[lme-final] mode               : $MODE  resume=$RESUME  dry_run=$DRY"

# --- hard prerequisites ------------------------------------------------- #
if [ "$DRY" -eq 0 ]; then
  : "${OPENROUTER_API_KEY:?[lme-final] export a valid OPENROUTER_API_KEY first}"
  : "${LONGMEMEVAL_DATA:?[lme-final] set LONGMEMEVAL_DATA to the LongMemEval-M full slice jsonl}"
else
  LONGMEMEVAL_DATA="${LONGMEMEVAL_DATA:-/path/to/longmemeval_m_full.jsonl}"
fi
LONGMEMEVAL_SRC="${LONGMEMEVAL_SRC:-data/longmemeval_m_cleaned.json}"

if [ "$DRY" -eq 0 ]; then
  if [ ! -f "$LONGMEMEVAL_DATA" ]; then
    echo "[lme-final] ERROR: LONGMEMEVAL_DATA not found: $LONGMEMEVAL_DATA" >&2
    exit 1
  fi
  if [ ! -f "$LONGMEMEVAL_SRC" ]; then
    echo "[lme-final] ERROR: LONGMEMEVAL_SRC not found: $LONGMEMEVAL_SRC" >&2
    exit 1
  fi
fi

# --- output dir + immutability guard ------------------------------------ #
if [ "$MODE" = "--smoke" ]; then
  if [ "$RUN_SCOPE" = "controller-only" ]; then
    RUN_ID="lme_smoke_controller_v12_qwen_2item"
  else
    RUN_ID="lme_smoke_v12_qwen_2item"
  fi
  SAMPLE_TO_OVERRIDE=1     # items 0..1 (2 questions)
  SHARDS_DEFAULT=2
else
  if [ "$RUN_SCOPE" = "controller-only" ]; then
    RUN_ID="lme_final_controller_v12_qwen_180"
  else
    RUN_ID="lme_final_5systems_v12_qwen_180"
  fi
  SAMPLE_TO_OVERRIDE=""    # full slice range 0..N-1
  SHARDS_DEFAULT=8
fi
OUT="runs_local/${RUN_ID}"
SHARDS="${SHARDS:-$SHARDS_DEFAULT}"

if [ -d "$OUT" ] && [ -n "$(ls -A "$OUT" 2>/dev/null)" ] && [ "$RESUME" -eq 0 ] && [ "$DRY" -eq 0 ]; then
  echo "[lme-final] ERROR: final output dir '$OUT' exists and is non-empty." >&2
  echo "[lme-final] Refusing to overwrite a final run. Use --resume to continue it," >&2
  echo "[lme-final] or move/remove '$OUT' to start fresh." >&2
  exit 1
fi
# Do not create the output dir on a dry-run (keep dry-runs side-effect free).
[ "$DRY" -eq 0 ] && mkdir -p "$OUT"

# --- build stratified slice (once; deterministic seed 0) ---------------- #
STRAT_SLICE="${LONGMEMEVAL_STRATIFIED_SLICE:-runs_local/_inputs/longmemeval_m_strat30_seed${SEED}.jsonl}"
if [ ! -f "$STRAT_SLICE" ]; then
  if [ "$DRY" -eq 1 ]; then
    echo "[lme-final] (dry-run) would build $STRAT_SLICE (30/competency, seed $SEED) from $LONGMEMEVAL_DATA"
  else
    echo "[lme-final] building $STRAT_SLICE (30/competency, seed $SEED) from $LONGMEMEVAL_DATA"
    mkdir -p "$(dirname "$STRAT_SLICE")"
    "$PYTHON" scripts/build_stratified_slice.py \
      --src "$LONGMEMEVAL_DATA" --out "$STRAT_SLICE" \
      --per-competency 30 --seed "$SEED"
  fi
else
  echo "[lme-final] reusing existing $STRAT_SLICE"
fi

# rows / range
if [ -f "$STRAT_SLICE" ]; then
  ROWS="$("$PYTHON" - "$STRAT_SLICE" <<'PY'
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    print(sum(1 for _ in handle))
PY
)"
else
  ROWS=180
fi

# The frozen evaluation is defined by exactly 30 questions from each of the six
# competencies. Validate a reused/custom slice before any paid request starts.
if [ -f "$STRAT_SLICE" ]; then
  "$PYTHON" - "$STRAT_SLICE" <<'PY'
import collections
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected = {
    "knowledge-update": 30,
    "multi-session": 30,
    "single-session-assistant": 30,
    "single-session-preference": 30,
    "single-session-user": 30,
    "temporal-reasoning": 30,
}
errors = []
ids = []
counts = collections.Counter()
row_count = 0
with path.open(encoding="utf-8") as handle:
    for index, line in enumerate(handle):
        if not line.strip():
            errors.append(f"row {index} is blank")
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"row {index} is invalid JSON: {exc.msg}")
            continue
        if not isinstance(row, dict):
            errors.append(f"row {index} is not a JSON object")
            continue
        row_count += 1
        ids.append(str(row.get("session_id") or ""))
        counts[str(row.get("competency") or "")] += 1
        corpus = row.get("corpus_sessions") or []
        if not isinstance(corpus, list) or any(
            not isinstance(item, dict) for item in corpus
        ):
            errors.append(f"row {index} has an invalid corpus_sessions value")
            corpus_ids = []
        else:
            corpus_ids = [str(item.get("session_id") or "") for item in corpus]
        supporting_value = row.get("supporting_session_ids") or []
        if not isinstance(supporting_value, list):
            errors.append(f"row {index} has an invalid supporting_session_ids value")
            supporting = set()
        else:
            supporting = {str(item) for item in supporting_value}
        if not str(row.get("question") or "").strip():
            errors.append(f"row {index} has an empty question")
        if not str(row.get("gold_answer") or "").strip():
            errors.append(f"row {index} has an empty gold_answer")
        if not corpus_ids or not all(corpus_ids):
            errors.append(f"row {index} has missing/empty corpus session IDs")
        missing_support = supporting - set(corpus_ids)
        if missing_support:
            errors.append(
                f"row {index} supporting IDs absent from corpus: "
                f"{sorted(missing_support)[:3]}"
            )
if row_count != 180:
    errors.append(f"row count is {row_count}, expected 180")
if not all(ids):
    errors.append("one or more rows lack session_id")
if len(ids) != len(set(ids)):
    errors.append("duplicate session_id values")
if dict(counts) != expected:
    errors.append(f"competency counts are {dict(sorted(counts.items()))}, expected {expected}")
if errors:
    displayed = errors[:10]
    if len(errors) > len(displayed):
        displayed.append(f"... and {len(errors) - len(displayed)} more error(s)")
    raise SystemExit("[lme-final] invalid frozen slice:\n- " + "\n- ".join(displayed))
print(f"[lme-final] frozen slice preflight ok: rows={row_count} competencies=6x30")
PY
fi
SAMPLE_TO=$(( ROWS - 1 ))
if [ -n "$SAMPLE_TO_OVERRIDE" ]; then SAMPLE_TO="$SAMPLE_TO_OVERRIDE"; fi
RUN_N=$(( SAMPLE_TO + 1 ))
# Let the range runner materialize OUT/range_0_N.jsonl. Downstream SSP analysis
# and reviewer packaging both expect that exact evaluated-slice artifact.
RANGE_OVERRIDE=""
echo "[lme-final] slice rows=$ROWS -> range 0..$SAMPLE_TO ; shards=$SHARDS ; out=$OUT"

# --- immutable, secret-free run manifest ------------------------------- #
if [ "$DRY" -eq 0 ]; then
  "$PYTHON" - "$OUT" "$STRAT_SLICE" "$SAMPLE_TO" "$MAIN_MODEL" "$ANSWER_MODEL" \
    "$JUDGE_PRIMARY" "$JUDGE_FALLBACK" "$ANSWER_ESCALATION" "$EMBED_ST" \
    "$LONGMEMEVAL_DATA" "$LONGMEMEVAL_SRC" "$SYSTEMS" "$MODE" "$SHARDS" "$RESUME" <<'PY'
import datetime as dt
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path

import yaml

(
    out,
    slice_arg,
    sample_to,
    main,
    answer_model,
    judge_primary,
    judge_fallback,
    escalation,
    embedder,
    full_source_arg,
    cleaned_source_arg,
    systems_arg,
    mode,
    shards,
    resume,
) = sys.argv[1:]
root = Path(out)
slice_path = Path(slice_arg).resolve()
full_source_path = Path(full_source_arg).resolve()
selected_systems = [item.strip() for item in systems_arg.split(",") if item.strip()]

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(roots: list[Path]) -> str:
    digest = hashlib.sha256()
    paths = sorted(
        path
        for tree in roots
        for path in tree.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    for path in paths:
        rel = path.as_posix().encode()
        digest.update(rel + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def package_versions(names: tuple[str, ...]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return versions

ids = []
with slice_path.open(encoding="utf-8") as handle:
    for index, line in enumerate(handle):
        if index > int(sample_to):
            break
        if line.strip():
            row = json.loads(line)
            ids.append(str(row.get("session_id")))
if not ids or any(item == "None" for item in ids):
    raise SystemExit("[lme-final] selected slice contains a missing session_id")
if len(ids) != len(set(ids)):
    raise SystemExit("[lme-final] selected slice contains duplicate session_ids")
ids_hash = hashlib.sha256("\n".join(ids).encode()).hexdigest()
slice_hash = sha256_file(slice_path)
full_source_hash = sha256_file(full_source_path)
config_path = Path("configs/release/final.yaml")
config_hash = sha256_file(config_path)
config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
expected_config = {
    "freeze_version": config["freeze"]["version"],
    "main_model": config["models"]["main_model"],
    "fast_model": config["models"]["fast_model"],
    "big_model": config["models"]["big_model"],
    "answer_model": config["models"]["answer_model"],
    "answer_escalation_model": config["models"]["answer_escalation_model"],
    "judge_primary": config["judge"]["primary_model"],
    "judge_fallback": config["judge"].get("fallback_model") or None,
    "embedder": config["embedder"]["model"],
    "embedder_device": config["embedder"]["device"],
    "embedder_max_seq_length": int(config["embedder"]["max_seq_length"]),
    "embedder_batch_size": int(config["embedder"]["batch_size"]),
    "embedder_client_batch_size": int(config["embedder"]["client_batch_size"]),
    "embedder_loopback_proxy_bypass": bool(
        config["embedder"]["loopback_proxy_bypass"]
    ),
    "seed": int(config["seed"]),
    "retry_max_attempts": int(config["retry"]["max_attempts"]),
    "retry_initial_delay_seconds": int(config["retry"]["backoff_base_seconds"]),
    "retry_max_delay_seconds": int(config["retry"]["backoff_cap_seconds"]),
    "shards": int(
        config["run"]["smoke_shards"]
        if mode == "--smoke"
        else config["run"]["shards"]
    ),
    "provider_order": list(config["models"]["request"]["provider_order"]),
    "provider_only": list(config["models"]["request"]["provider_only"]),
    "provider_fallbacks": bool(config["models"]["request"]["provider_fallbacks"]),
    "temperature": float(config["models"]["request"]["temperature"]),
    "reasoning_enabled": bool(config["models"]["request"]["reasoning_enabled"]),
    "timeout_seconds": int(config["models"]["request"]["timeout_seconds"]),
    "answer_max_new_tokens": int(config["models"]["answer_request"]["max_new_tokens"]),
    "answer_reasoning_enabled": bool(config["models"]["answer_request"]["reasoning_enabled"]),
    "answer_provider_order": list(config["models"]["answer_request"]["provider_order"]),
    "answer_provider_only": list(config["models"]["answer_request"]["provider_only"]),
    "answer_provider_fallbacks": bool(config["models"]["answer_request"]["provider_fallbacks"]),
    "extraction_concurrency": int(config["run"]["extraction_concurrency"]),
    "retrieval_k": int(config["run"]["retrieval_k"]),
    "controller_memory_top_k": int(config["run"]["controller_memory_top_k"]),
    "answer_context_max_tokens": int(config["run"]["answer_context_max_tokens"]),
    "answer_context_session_cap": int(config["run"]["answer_context_session_cap"]),
    "history_retrieval_k": int(config["run"]["history_retrieval_k"]),
    "extraction_max_new_tokens": int(config["run"]["extraction_max_new_tokens"]),
    "relation_max_new_tokens": int(config["run"]["relation_max_new_tokens"]),
    "openai_max_model_len": int(config["run"]["openai_max_model_len"]),
    "v7_fixes": bool(config["run"]["v7_fixes"]),
    "v8_fixes": bool(config["run"]["v8_fixes"]),
    "v9_fixes": bool(config["run"]["v9_fixes"]),
    "competency_user_candidate_k": int(config["run"]["competency_user_candidate_k"]),
    "competency_assistant_candidate_k": int(
        config["run"]["competency_assistant_candidate_k"]
    ),
    "competency_session_top_k": int(config["run"]["competency_session_top_k"]),
    "competency_preference_session_top_k": int(
        config["run"]["competency_preference_session_top_k"]
    ),
    "enable_thinking": bool(config["run"]["enable_thinking"]),
    "shard_retries": int(config["retry"]["shard_retries"]),
    "shard_retry_backoff_seconds": int(config["retry"]["shard_retry_backoff_seconds"]),
    "accuracy_threshold": float(config["acceptance"]["controller_accuracy_threshold"]),
    "accuracy_required_correct": int(config["acceptance"]["controller_required_correct"]),
    "accuracy_expected_n": int(config["acceptance"]["expected_n"]),
    "accuracy_gate": config["acceptance"]["gate"],
    "accuracy_full_run_only": bool(config["acceptance"]["full_run_only"]),
}
allowed_system_sets = {
    name: list(systems)
    for name, systems in config["run"]["allowed_system_sets"].items()
}
if selected_systems not in allowed_system_sets.values():
    raise SystemExit(
        "[lme-final] selected systems are not a frozen scope: "
        + json.dumps(selected_systems)
    )
executed_config = {
    "freeze_version": "final-2.0",
    "main_model": main,
    "fast_model": main,
    "big_model": main,
    "answer_model": answer_model,
    "answer_escalation_model": escalation,
    "judge_primary": judge_primary,
    "judge_fallback": judge_fallback or None,
    "embedder": embedder,
    "embedder_device": "cpu",
    "embedder_max_seq_length": 256,
    "embedder_batch_size": 128,
    "embedder_client_batch_size": 128,
    "embedder_loopback_proxy_bypass": True,
    "seed": 0,
    "retry_max_attempts": 5,
    "retry_initial_delay_seconds": 2,
    "retry_max_delay_seconds": 60,
    "shards": int(shards),
    "provider_order": [],
    "provider_only": ["venice", "deepinfra", "siliconflow"],
    "provider_fallbacks": True,
    "temperature": 0.0,
    "reasoning_enabled": False,
    "timeout_seconds": 300,
    "answer_max_new_tokens": 4096,
    "answer_reasoning_enabled": False,
    "answer_provider_order": [],
    "answer_provider_only": ["venice", "deepinfra", "siliconflow"],
    "answer_provider_fallbacks": True,
    "extraction_concurrency": 4,
    "retrieval_k": 16,
    "controller_memory_top_k": 64,
    "answer_context_max_tokens": 40000,
    "answer_context_session_cap": 4,
    "history_retrieval_k": 4,
    "extraction_max_new_tokens": 512,
    "relation_max_new_tokens": 256,
    "openai_max_model_len": 65536,
    "v7_fixes": True,
    "v8_fixes": True,
    "v9_fixes": True,
    "competency_user_candidate_k": 120,
    "competency_assistant_candidate_k": 60,
    "competency_session_top_k": 12,
    "competency_preference_session_top_k": 18,
    "enable_thinking": False,
    "shard_retries": 2,
    "shard_retry_backoff_seconds": 5,
    "accuracy_threshold": 0.85,
    "accuracy_required_correct": 153,
    "accuracy_expected_n": 180,
    "accuracy_gate": "scripts/analysis/check_controller_accuracy_gate.py",
    "accuracy_full_run_only": True,
}
if expected_config != executed_config:
    raise SystemExit(
        "[lme-final] wrapper/config drift:\n"
        + json.dumps(
            {"frozen_yaml": expected_config, "wrapper": executed_config},
            indent=2,
            sort_keys=True,
        )
    )

hashed_code_paths = [
    Path("configs/models/openrouter_qwen_gemma.yaml"),
    Path("FINAL_EVALUATION_PROTOCOL.md"),
    Path("FINAL_ANALYSIS_PLAN.md"),
    Path("FINAL_METRIC_DEFINITIONS.md"),
    Path("FINAL_RUN_MATRIX.yaml"),
    Path("scripts/evaluation/run_longmemeval_final.sh"),
    Path("deploy/run_colab_modal_range.sh"),
    Path("scripts/run_vllm_cascade.py"),
    Path("scripts/run_baseline.py"),
    Path("scripts/verify_homogeneous_run.py"),
    Path("scripts/analysis/check_controller_accuracy_gate.py"),
    Path("src/ksa/baselines/embeddings.py"),
    Path("src/ksa/controller/computation.py"),
    Path("src/ksa/eval/longmemeval.py"),
    Path("src/ksa/eval/merge.py"),
    Path("src/ksa/inference/openai_compatible.py"),
    Path("src/ksa/pipeline/orchestrator.py"),
]
code_hashes = {str(path): sha256_file(path) for path in hashed_code_paths}
prompt_bundle_hash = sha256_tree(
    [Path("prompts"), Path("src/ksa/baselines/prompts")]
)
try:
    git_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()
    git_dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    )
except (OSError, subprocess.CalledProcessError):
    git_head, git_dirty = None, None

manifest_path = root / "manifest.json"
frozen = {
    "freeze_version": "final-2.0",
    "config_path": str(config_path),
    "config_sha256": config_hash,
    "code_and_protocol_sha256": code_hashes,
    "prompt_bundle_sha256": prompt_bundle_hash,
    "main_model": main,
    "answer_model": answer_model,
    "answer_escalation_model": escalation,
    "answer_provider_policy": {
        "allow_fallbacks": True,
        "provider_order": [],
        "provider_only": ["venice", "deepinfra", "siliconflow"],
        "reasoning_enabled": False,
    },
    "answer_max_new_tokens": 4096,
    "answer_context_max_tokens": 40000,
    "openai_max_model_len": 65536,
    "controller_retrieval_policy": {
        "version": "v12",
        "retrieval_k": 16,
        "memory_top_k": 64,
        "history_retrieval_k": 4,
        "answer_context_session_cap": 4,
        "competency_user_candidate_k": 120,
        "competency_assistant_candidate_k": 60,
        "competency_session_top_k": 12,
        "competency_preference_session_top_k": 18,
    },
    "controller_accuracy_acceptance": {
        "threshold": 0.85,
        "required_correct": 153,
        "expected_n": 180,
        "gate": "scripts/analysis/check_controller_accuracy_gate.py",
    },
    "judge_primary": judge_primary,
    "judge_fallback": judge_fallback or None,
    "judge_fallback_trigger": "disabled_fail_shard_after_primary_retries",
    "embedder": {
        "model": embedder,
        "device": "cpu",
        "max_seq_length": 256,
        "batch_size": 128,
        "client_batch_size": 128,
        "loopback_proxy_bypass": True,
    },
    "retry_policy": {
        "per_request_max_attempts": 5,
        "initial_delay_seconds": 2,
        "max_delay_seconds": 60,
        "shard_retries": 2,
        "shard_retry_backoff_seconds": 5,
    },
    "full_source_sha256": full_source_hash,
    "slice_sha256": slice_hash,
    "evaluated_session_ids_sha256": ids_hash,
    "evaluated_n": len(ids),
    "evaluated_systems": selected_systems,
    "shards": int(shards),
}
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prior = {key: manifest.get(key) for key in frozen}
    if prior != frozen:
        raise SystemExit(
            "[lme-final] refusing resume: manifest differs from frozen inputs/config"
        )
    if resume != "1":
        raise SystemExit("[lme-final] manifest exists but --resume was not supplied")
else:
    manifest = {
        **frozen,
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "slice_path_local_not_redistributed": str(slice_path),
        "full_source_path_local_not_redistributed": str(full_source_path),
        "cleaned_source_path_local_not_redistributed": str(
            Path(cleaned_source_arg).resolve()
        ),
        "git_head": git_head,
        "git_dirty_at_start": git_dirty,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "packages": package_versions(
                ("numpy", "pydantic", "PyYAML", "sentence-transformers", "torch")
            ),
        },
        "status": "running",
        "attempts": [],
    }
manifest["status"] = "running"
manifest.setdefault("attempts", []).append(
    {"started_at_utc": dt.datetime.now(dt.UTC).isoformat(), "resume": resume == "1"}
)
tmp = manifest_path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
tmp.replace(manifest_path)
print(f"[lme-final] wrote secret-free manifest: {manifest_path}")
PY
fi

mark_manifest_on_exit() {
  local exit_code=$?
  trap - EXIT
  if [ "$DRY" -eq 0 ] && [ "$exit_code" -ne 0 ] && [ -f "$OUT/manifest.json" ]; then
    "$PYTHON" - "$OUT/manifest.json" "$exit_code" <<'PY'
import datetime as dt
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
manifest = json.loads(path.read_text(encoding="utf-8"))
manifest["status"] = "failed"
manifest["failed_at_utc"] = dt.datetime.now(dt.UTC).isoformat()
manifest["exit_code"] = int(sys.argv[2])
tmp = path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
tmp.replace(path)
PY
  fi
  exit "$exit_code"
}
trap mark_manifest_on_exit EXIT

# --- assemble the frozen env block for the real underlying runner ------- #
run_underlying() {
  PYTHON="$PYTHON" \
  OPENROUTER_BASE_URL=https://openrouter.ai/api/v1 \
  FAST_BASE_URL=https://openrouter.ai/api/v1 \
  BIG_BASE_URL=https://openrouter.ai/api/v1 \
  JUDGE_OPENAI_BASE_URL=https://openrouter.ai/api/v1 \
  JUDGE_OPENAI_API_KEY_ENV=OPENROUTER_API_KEY \
  JUDGE_OPENAI_CHAT_TEMPLATE_KWARGS_JSON='' \
  JUDGE_OPENAI_EXTRA_BODY_JSON='{"reasoning":{"enabled":false}}' \
  OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-DRYRUN}" \
  OPENAI_API_KEY_ENV=OPENROUTER_API_KEY \
  OPENMODEL_PRIMARY=0 \
  OPENAI_EXTRA_BODY_JSON="$MEMORY_PROVIDER_POLICY_JSON" \
  OPENAI_CHAT_TEMPLATE_KWARGS_JSON='{"enable_thinking":false}' \
  ANSWER_MODEL="$ANSWER_MODEL" \
  ANSWER_MAX_NEW_TOKENS=4096 \
  ANSWER_OPENAI_EXTRA_BODY_JSON="$ANSWER_PROVIDER_POLICY_JSON" \
  FAST_MODEL="$MAIN_MODEL" \
  BIG_MODEL="$MAIN_MODEL" \
  ANSWER_ESCALATION_BASE_URL=https://openrouter.ai/api/v1 \
  ANSWER_ESCALATION_MODEL="$ANSWER_ESCALATION" \
  JUDGE_MODEL="$JUDGE_PRIMARY" \
  JUDGE_OPENAI_FALLBACK_MODEL="$JUDGE_FALLBACK" \
  EXTRACTION_MAX_NEW_TOKENS=512 \
  RELATION_MAX_NEW_TOKENS=256 \
  OPENAI_MAX_MODEL_LEN=65536 \
  OPENAI_RETRY_MAX_ATTEMPTS=5 \
  OPENAI_RETRY_INITIAL_DELAY_S=2 \
  OPENAI_RETRY_MAX_DELAY_S=60 \
  OPENAI_TIMEOUT_S=300 \
  RETRIEVAL_K=16 \
  CONTROLLER_MEMORY_TOP_K=64 \
  EXTRACTION_CONCURRENCY=4 \
  ANSWER_CONTEXT_MAX_TOKENS=40000 \
  V7_FIXES=1 \
  V8_FIXES=1 \
  V9_FIXES=1 \
  HISTORY_RETRIEVAL_K=4 \
  ANSWER_CONTEXT_SESSION_CAP=4 \
  COMPETENCY_USER_CANDIDATE_K=120 \
  COMPETENCY_ASSISTANT_CANDIDATE_K=60 \
  COMPETENCY_SESSION_TOP_K=12 \
  COMPETENCY_PREFERENCE_SESSION_TOP_K=18 \
  SHARD_RETRIES=2 \
  SHARD_RETRY_BACKOFF_S=5 \
  SHARED_EXTRACTION_CACHE="${OUT}/_shared_extraction_cache.jsonl" \
  SEED=0 \
  DATASET=m \
  SRC="$LONGMEMEVAL_SRC" \
  SLICE="$STRAT_SLICE" \
  RANGE_SLICE_OVERRIDE="$RANGE_OVERRIDE" \
  OUT="$OUT" \
  SAMPLE_FROM=0 SAMPLE_TO="$SAMPLE_TO" \
  SYSTEMS="$SYSTEMS" \
  SHARDS="$SHARDS" \
  START_EMBED_SERVER=1 \
  EMBED_MODEL_PATH="$EMBED_ST" \
  EMBED_MODEL_NAME=minilm \
  EMBED_TASK="" \
  EMBED_DEVICE=cpu \
  EMBED_MAX_SEQ_LENGTH=256 \
  EMBED_BATCH_SIZE=128 EMBED_CLIENT_BATCH_SIZE=128 \
  bash deploy/run_colab_modal_range.sh
}

if [ "$DRY" -eq 1 ]; then
  echo "[lme-final] DRY-RUN: would invoke deploy/run_colab_modal_range.sh with the frozen env above:"
  echo "  SYSTEMS=$SYSTEMS SHARDS=$SHARDS SAMPLE_FROM=0 SAMPLE_TO=$SAMPLE_TO"
  echo "  SLICE=$STRAT_SLICE OUT=$OUT SRC=$LONGMEMEVAL_SRC"
  echo "  JUDGE_MODEL=$JUDGE_PRIMARY JUDGE_OPENAI_FALLBACK_MODEL=<disabled>"
  echo "  FAST_MODEL=BIG_MODEL=$MAIN_MODEL ANSWER_MODEL=ANSWER_ESCALATION_MODEL=$ANSWER_MODEL"
  echo "  ANSWER_MAX_NEW_TOKENS=4096 EMBED_MODEL_PATH=$EMBED_ST (cpu)"
  echo "  post-run controller gate: >=${ACCURACY_REQUIRED_CORRECT}/180 (${ACCURACY_THRESHOLD})"
  echo "  memory/answer provider pool=$MEMORY_PROVIDER_SLUGS; reasoning disabled"
  echo "[lme-final] DRY-RUN complete; nothing executed."
  exit 0
fi

run_underlying

# --- homogeneity + coverage gate ---------------------------------------- #
echo "[lme-final] verifying homogeneity ..."
JUDGE_VERIFY_ARGS=()
if [ -n "$JUDGE_FALLBACK" ]; then
  JUDGE_VERIFY_ARGS+=(--allowed-judge-fallback "$JUDGE_FALLBACK")
fi
"$PYTHON" scripts/verify_homogeneous_run.py \
  --run-root "$OUT" --slice "$STRAT_SLICE" \
  --sample-from 0 --sample-to "$SAMPLE_TO" \
  --systems "$SYSTEMS" --expected-n "$RUN_N" \
  --expected-answer-model "$ANSWER_MODEL" \
  --allowed-auxiliary-model "$MAIN_MODEL" \
  --expected-judge-primary "$JUDGE_PRIMARY" \
  "${JUDGE_VERIFY_ARGS[@]}"

# --- explicit controller >=85% acceptance gate (full runs only) -------- #
ACCURACY_GATE_PATH="$OUT/controller_accuracy_gate.json"
ACCURACY_GATE_RC=0
ACCURACY_GATE_STATUS="not_applicable_smoke"
if [ "$MODE" = "--full" ]; then
  echo "[lme-final] checking controller accuracy target ..."
  set +e
  "$PYTHON" scripts/analysis/check_controller_accuracy_gate.py \
    --run-root "$OUT" --expected-n "$RUN_N" \
    --threshold "$ACCURACY_THRESHOLD" --out "$ACCURACY_GATE_PATH"
  ACCURACY_GATE_RC=$?
  set -e
  case "$ACCURACY_GATE_RC" in
    0) ACCURACY_GATE_STATUS="passed" ;;
    1) ACCURACY_GATE_STATUS="below_target" ;;
    *) ACCURACY_GATE_STATUS="gate_error" ;;
  esac
fi

# --- atomic summary write ----------------------------------------------- #
SUMMARY="$OUT/final_summary.json"
TMP="$SUMMARY.tmp"
"$PYTHON" - "$OUT" "$MAIN_MODEL" "$ANSWER_MODEL" "$JUDGE_PRIMARY" \
  "$JUDGE_FALLBACK" "$MODE" "$RUN_N" "$ACCURACY_THRESHOLD" \
  "$ACCURACY_REQUIRED_CORRECT" "$ACCURACY_GATE_STATUS" > "$TMP" <<'PY'
import json, sys
from pathlib import Path
(
    out,
    main_model,
    answer_model,
    jp,
    jf,
    mode,
    expected_n,
    threshold,
    required_correct,
    gate_status,
) = sys.argv[1:]
root = Path(out)
systems = {}
for sysdir in sorted(p for p in root.iterdir() if p.is_dir()):
    rep = sysdir / "report.json"
    if rep.exists():
        try:
            r = json.loads(rep.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(r, dict):
            continue
        systems[sysdir.name] = {
            "n_sessions": r.get("n_sessions"),
            "overall_accuracy": r.get("overall_accuracy"),
            "judge_model_id": r.get("judge_model_id"),
        }
gate_path = root / "controller_accuracy_gate.json"
gate = None
if gate_path.is_file():
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
print(json.dumps({
    "run": root.name,
    "frozen_config": "configs/release/final.yaml",
    "main_model": main_model,
    "answer_model": answer_model,
    "judge_primary": jp,
    "judge_fallback": jf or None,
    "controller_accuracy_acceptance": {
        "applies": mode == "--full",
        "expected_n": int(expected_n),
        "gate": gate,
        "required_correct": int(required_correct),
        "status": gate_status,
        "threshold": float(threshold),
    },
    "systems": systems,
    "note": "raw homogeneous numbers; apply FINAL_ANALYSIS_PLAN.md before citing.",
}, indent=2, sort_keys=True))
PY
mv "$TMP" "$SUMMARY"
echo "[lme-final] wrote $SUMMARY"
"$PYTHON" - "$OUT/manifest.json" "$MODE" "$ACCURACY_GATE_STATUS" \
  "$ACCURACY_GATE_RC" "$ACCURACY_GATE_PATH" <<'PY'
import datetime as dt
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
mode = sys.argv[2]
gate_status = sys.argv[3]
gate_rc = int(sys.argv[4])
gate_path = Path(sys.argv[5])
manifest = json.loads(path.read_text(encoding="utf-8"))
if mode == "--smoke":
    status = "completed_homogeneity_verified_smoke"
elif gate_status == "passed":
    status = "completed_homogeneity_and_accuracy_verified"
elif gate_status == "below_target":
    status = "completed_homogeneity_verified_accuracy_below_target"
else:
    status = "completed_homogeneity_verified_accuracy_gate_error"
manifest["status"] = status
manifest["accuracy_gate_exit_code"] = gate_rc
manifest["accuracy_gate_status"] = gate_status
if gate_path.is_file():
    manifest["accuracy_gate_result"] = json.loads(
        gate_path.read_text(encoding="utf-8")
    )
manifest["completed_at_utc"] = dt.datetime.now(dt.UTC).isoformat()
manifest.pop("failed_at_utc", None)
manifest.pop("exit_code", None)
tmp = path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
tmp.replace(path)
PY
trap - EXIT
echo "[lme-final] NEXT: bash scripts/evaluation/run_judge_audit.sh $OUT"
if [ "$ACCURACY_GATE_RC" -ne 0 ]; then
  echo "[lme-final] ERROR: full run completed but controller accuracy gate status is $ACCURACY_GATE_STATUS." >&2
  echo "[lme-final] Share $SUMMARY and $ACCURACY_GATE_PATH for diagnosis." >&2
  exit "$ACCURACY_GATE_RC"
fi
echo "[lme-final] SUCCESS: homogeneity and all applicable acceptance gates passed."
