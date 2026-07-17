#!/usr/bin/env bash
# FROZEN homogeneous LongMemEval-M rerun: all five systems
# (controller, b4, b3, b2, b1) on the SAME 180-question stratified slice, ONE
# configuration, ONE judge policy, NO failure-replay patching, NO adjudication
# baked into the numbers. This is the only path to a first final-candidate
# LongMemEval result; the v7 diagnostic and contradicted 77.2% failure-replay
# construction are not prior final results.
#
# Config is pinned to configs/release/final.yaml. Underlying real entry points:
#   deploy/run_colab_modal_range.sh -> scripts/run_vllm_cascade.py
#   (+ scripts/serve_embeddings.py for the local MiniLM embed server).
#
# This wrapper OVERRIDES the legacy deploy judge (which hardcodes the non-free
# route with no fallback) to the frozen judge policy:
#   primary  = google/gemma-4-31b-it:free
#   fallback = google/gemma-4-31b-it   (fires ONLY on operational failure)
#
# HARD PREREQUISITES (the script refuses to run without them):
#   1. OPENROUTER_API_KEY  -- a newly authorized key. The credential tested on
#                              2026-07-13 returned HTTP 403 and must not be reused.
#   2. LONGMEMEVAL_DATA     -- path to the LongMemEval-M full slice jsonl
#                              (external data; not redistributed in this repo).
#      Optionally LONGMEMEVAL_SRC -> the cleaned source json
#      (default data/longmemeval_m_cleaned.json), required by the underlying
#      range runner's existence check.
#
# Usage:
#   OPENROUTER_API_KEY=sk-or-... LONGMEMEVAL_DATA=/path/longmemeval_m_full.jsonl \
#     bash scripts/evaluation/run_longmemeval_final.sh --full
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
for arg in "$@"; do
  case "$arg" in
    --full) MODE="--full" ;;
    --smoke) MODE="--smoke" ;;
    --resume) RESUME=1 ;;
    --dry-run) DRY=1 ;;
    *) echo "[lme-final] unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# --- frozen models / judge / embedder ---------------------------------- #
MAIN_MODEL="qwen/qwen3.5-9b"
JUDGE_PRIMARY="google/gemma-4-31b-it:free"
JUDGE_FALLBACK="google/gemma-4-31b-it"
# Retry uses the same frozen model. This preserves the answer-contract retry
# without introducing a heterogeneous 35B answerer into only two systems.
ANSWER_ESCALATION="$MAIN_MODEL"
EMBED_ST="sentence-transformers/all-MiniLM-L6-v2"
SEED=0

echo "[lme-final] ===== FROZEN CONFIG (configs/release/final.yaml) ====="
echo "[lme-final] main model       : $MAIN_MODEL (answerer/extractor/relation)"
echo "[lme-final] judge primary     : $JUDGE_PRIMARY"
echo "[lme-final] judge fallback     : $JUDGE_FALLBACK (operational failure only)"
echo "[lme-final] answer escalation  : $ANSWER_ESCALATION"
echo "[lme-final] embedder           : $EMBED_ST (MiniLM-L6-v2, cpu)"
echo "[lme-final] seed               : $SEED"
echo "[lme-final] mode               : $MODE  resume=$RESUME  dry_run=$DRY"

# --- hard prerequisites ------------------------------------------------- #
if [ "$DRY" -eq 0 ]; then
  : "${OPENROUTER_API_KEY:?[lme-final] export a ROTATED OPENROUTER_API_KEY first}"
  : "${LONGMEMEVAL_DATA:?[lme-final] set LONGMEMEVAL_DATA to the LongMemEval-M full slice jsonl}"
else
  LONGMEMEVAL_DATA="${LONGMEMEVAL_DATA:-/path/to/longmemeval_m_full.jsonl}"
fi
LONGMEMEVAL_SRC="${LONGMEMEVAL_SRC:-data/longmemeval_m_cleaned.json}"

if [ "$DRY" -eq 0 ] && [ ! -f "$LONGMEMEVAL_DATA" ]; then
  echo "[lme-final] ERROR: LONGMEMEVAL_DATA not found: $LONGMEMEVAL_DATA" >&2
  exit 1
fi

# --- output dir + immutability guard ------------------------------------ #
if [ "$MODE" = "--smoke" ]; then
  RUN_ID="lme_smoke_2item"
  SAMPLE_TO_OVERRIDE=1     # items 0..1 (2 questions)
  SHARDS_DEFAULT=2
else
  RUN_ID="lme_final_5systems_180"
  SAMPLE_TO_OVERRIDE=""    # full slice range 0..N-1
  SHARDS_DEFAULT=10
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
print(sum(1 for _ in open(sys.argv[1], encoding="utf-8")))
PY
)"
else
  ROWS=180
fi
SAMPLE_TO=$(( ROWS - 1 ))
if [ -n "$SAMPLE_TO_OVERRIDE" ]; then SAMPLE_TO="$SAMPLE_TO_OVERRIDE"; fi
RUN_N=$(( SAMPLE_TO + 1 ))
RANGE_OVERRIDE=""
if [ "$RUN_N" -eq "$ROWS" ]; then RANGE_OVERRIDE="$STRAT_SLICE"; fi
echo "[lme-final] slice rows=$ROWS -> range 0..$SAMPLE_TO ; shards=$SHARDS ; out=$OUT"

# --- immutable, secret-free run manifest ------------------------------- #
if [ "$DRY" -eq 0 ]; then
  "$PYTHON" - "$OUT" "$STRAT_SLICE" "$SAMPLE_TO" "$MAIN_MODEL" \
    "$JUDGE_PRIMARY" "$JUDGE_FALLBACK" "$ANSWER_ESCALATION" "$EMBED_ST" \
    "$LONGMEMEVAL_DATA" "$LONGMEMEVAL_SRC" "$RESUME" <<'PY'
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
    judge_primary,
    judge_fallback,
    escalation,
    embedder,
    full_source_arg,
    cleaned_source_arg,
    resume,
) = sys.argv[1:]
root = Path(out)
slice_path = Path(slice_arg).resolve()
full_source_path = Path(full_source_arg).resolve()

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

rows = []
with slice_path.open(encoding="utf-8") as handle:
    for index, line in enumerate(handle):
        if index > int(sample_to):
            break
        if line.strip():
            rows.append(json.loads(line))
ids = [str(row.get("session_id")) for row in rows]
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
    "answer_escalation_model": config["models"]["answer_escalation_model"],
    "judge_primary": config["judge"]["primary_model"],
    "judge_fallback": config["judge"]["fallback_model"],
    "embedder": config["embedder"]["model"],
    "seed": int(config["seed"]),
    "retry_max_attempts": int(config["retry"]["max_attempts"]),
    "provider_order": list(config["models"]["request"]["provider_order"]),
    "provider_fallbacks": bool(config["models"]["request"]["provider_fallbacks"]),
}
executed_config = {
    "freeze_version": "final-1.1",
    "main_model": main,
    "fast_model": main,
    "big_model": main,
    "answer_escalation_model": escalation,
    "judge_primary": judge_primary,
    "judge_fallback": judge_fallback,
    "embedder": embedder,
    "seed": 0,
    "retry_max_attempts": 5,
    "provider_order": ["venice"],
    "provider_fallbacks": False,
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
    Path("src/ksa/eval/longmemeval.py"),
    Path("src/ksa/eval/merge.py"),
    Path("src/ksa/inference/openai_compatible.py"),
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
    "freeze_version": "final-1.1",
    "config_path": str(config_path),
    "config_sha256": config_hash,
    "code_and_protocol_sha256": code_hashes,
    "prompt_bundle_sha256": prompt_bundle_hash,
    "main_model": main,
    "answer_escalation_model": escalation,
    "answer_provider_policy": {
        "order": ["venice"],
        "only": ["venice"],
        "allow_fallbacks": False,
    },
    "judge_primary": judge_primary,
    "judge_fallback": judge_fallback,
    "judge_fallback_trigger": "operational_or_format_failure_after_primary_retries",
    "embedder": {"model": embedder, "device": "cpu", "max_seq_length": 256},
    "retry_policy": {
        "per_request_max_attempts": 5,
        "initial_delay_seconds": 2,
        "max_delay_seconds": 60,
        "shard_retries": 2,
    },
    "full_source_sha256": full_source_hash,
    "slice_sha256": slice_hash,
    "evaluated_session_ids_sha256": ids_hash,
    "evaluated_n": len(ids),
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
  JUDGE_OPENAI_EXTRA_BODY_JSON='{"reasoning":{"enabled":false}}' \
  OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-DRYRUN}" \
  OPENAI_API_KEY_ENV=OPENROUTER_API_KEY \
  OPENAI_EXTRA_BODY_JSON='{"provider":{"order":["venice"],"only":["venice"],"allow_fallbacks":false},"reasoning":{"enabled":false}}' \
  FAST_MODEL="$MAIN_MODEL" \
  BIG_MODEL="$MAIN_MODEL" \
  ANSWER_ESCALATION_BASE_URL=https://openrouter.ai/api/v1 \
  ANSWER_ESCALATION_MODEL="$ANSWER_ESCALATION" \
  JUDGE_MODEL="$JUDGE_PRIMARY" \
  JUDGE_OPENAI_FALLBACK_MODEL="$JUDGE_FALLBACK" \
  EXTRACTION_MAX_NEW_TOKENS=512 \
  RELATION_MAX_NEW_TOKENS=256 \
  OPENAI_MAX_MODEL_LEN=32768 \
  OPENAI_RETRY_MAX_ATTEMPTS=5 \
  OPENAI_RETRY_INITIAL_DELAY_S=2 \
  OPENAI_RETRY_MAX_DELAY_S=60 \
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
  DATASET=m \
  SRC="$LONGMEMEVAL_SRC" \
  SLICE="$STRAT_SLICE" \
  RANGE_SLICE_OVERRIDE="$RANGE_OVERRIDE" \
  OUT="$OUT" \
  SAMPLE_FROM=0 SAMPLE_TO="$SAMPLE_TO" \
  SYSTEMS="controller,b4,b3,b2,b1" \
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
  echo "  SYSTEMS=controller,b4,b3,b2,b1 SHARDS=$SHARDS SAMPLE_FROM=0 SAMPLE_TO=$SAMPLE_TO"
  echo "  SLICE=$STRAT_SLICE OUT=$OUT SRC=$LONGMEMEVAL_SRC"
  echo "  JUDGE_MODEL=$JUDGE_PRIMARY JUDGE_OPENAI_FALLBACK_MODEL=$JUDGE_FALLBACK"
  echo "  FAST_MODEL=BIG_MODEL=ANSWER_ESCALATION_MODEL=$MAIN_MODEL EMBED_MODEL_PATH=$EMBED_ST (cpu)"
  echo "[lme-final] DRY-RUN complete; nothing executed."
  exit 0
fi

run_underlying

# --- homogeneity + coverage gate ---------------------------------------- #
echo "[lme-final] verifying homogeneity ..."
"$PYTHON" scripts/verify_homogeneous_run.py \
  --run-root "$OUT" --slice "$STRAT_SLICE" \
  --sample-from 0 --sample-to "$SAMPLE_TO" \
  --systems controller,b4,b3,b2,b1 --expected-n "$RUN_N" \
  --expected-answer-model "$MAIN_MODEL" \
  --expected-answer-provider venice \
  --expected-judge-primary "$JUDGE_PRIMARY" \
  --allowed-judge-fallback "$JUDGE_FALLBACK"

# --- atomic summary write ----------------------------------------------- #
SUMMARY="$OUT/final_summary.json"
TMP="$SUMMARY.tmp"
"$PYTHON" - "$OUT" "$MAIN_MODEL" "$JUDGE_PRIMARY" "$JUDGE_FALLBACK" > "$TMP" <<'PY'
import json, sys
from pathlib import Path
out, main_model, jp, jf = sys.argv[1:5]
root = Path(out)
systems = {}
for sysdir in sorted(p for p in root.iterdir() if p.is_dir()):
    rep = sysdir / "report.json"
    if rep.exists():
        try:
            r = json.load(open(rep))
        except Exception:
            continue
        systems[sysdir.name] = {
            "n_sessions": r.get("n_sessions"),
            "overall_accuracy": r.get("overall_accuracy"),
            "judge_model_id": r.get("judge_model_id"),
        }
print(json.dumps({
    "run": root.name,
    "frozen_config": "configs/release/final.yaml",
    "main_model": main_model,
    "judge_primary": jp,
    "judge_fallback": jf,
    "systems": systems,
    "note": "raw homogeneous numbers; apply FINAL_ANALYSIS_PLAN.md before citing.",
}, indent=2, sort_keys=True))
PY
mv "$TMP" "$SUMMARY"
echo "[lme-final] wrote $SUMMARY"
"$PYTHON" - "$OUT/manifest.json" <<'PY'
import datetime as dt
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
manifest = json.loads(path.read_text(encoding="utf-8"))
manifest["status"] = "completed_and_homogeneity_verified"
manifest["completed_at_utc"] = dt.datetime.now(dt.UTC).isoformat()
tmp = path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
tmp.replace(path)
PY
trap - EXIT
echo "[lme-final] NEXT: bash scripts/evaluation/run_judge_audit.sh $OUT"
