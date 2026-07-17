#!/usr/bin/env bash
# Package a completed run directory for return/review: the run dir + its
# manifest + an environment report + a sha256 checksum list, tarred into
# return_package_<runid>.tar.gz .
#
# NEVER packages credentials: .env files and any *key* files are excluded, and
# the env report prints only whether keys are SET, never their values.
#
# Usage:
#   bash scripts/release/package_run_for_review.sh runs_local/lme_final_5systems_180
#
# macOS-compatible (BSD tar/shasum); python3 only.
set -euo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
cd "$REPO"

PYTHON="${PYTHON:-python3}"
if [ -x .venv/bin/python ]; then PYTHON=".venv/bin/python"; fi

RUN_DIR="${1:?usage: package_run_for_review.sh <run_dir under runs_local/>}"
if [ ! -d "$RUN_DIR" ]; then
  echo "[package] ERROR: run dir '$RUN_DIR' not found." >&2
  exit 1
fi
RUN_DIR_ABS="$(cd "$RUN_DIR" && pwd -P)"
RUNS_ROOT_ABS="$(mkdir -p "$REPO/runs_local" && cd "$REPO/runs_local" && pwd -P)"
case "$RUN_DIR_ABS/" in
  "$RUNS_ROOT_ABS"/*) ;;
  *)
    echo "[package] ERROR: run dir must be contained under $RUNS_ROOT_ABS" >&2
    exit 1
    ;;
esac
RUN_ID="$(basename "$RUN_DIR")"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/ksa_pkg_${RUN_ID}.XXXXXX")"
PKG_ROOT="$STAGE/return_package_$RUN_ID"
mkdir -p "$PKG_ROOT"

echo "[package] run id  : $RUN_ID"
echo "[package] run dir : $RUN_DIR"
echo "[package] staging : $PKG_ROOT"

# --- sha256 checksum for pick the right tool --------------------------- #
if command -v shasum >/dev/null 2>&1; then
  SHA() { shasum -a 256 "$@"; }
elif command -v sha256sum >/dev/null 2>&1; then
  SHA() { sha256sum "$@"; }
else
  echo "[package] ERROR: no shasum/sha256sum available." >&2
  exit 1
fi

# --- 1. copy only public aggregate artifacts --------------------------- #
mkdir -p "$PKG_ROOT/run"
for name in manifest.json final_summary.json homogeneity_report.json judge_audit.json; do
  [ -f "$RUN_DIR/$name" ] && cp "$RUN_DIR/$name" "$PKG_ROOT/run/$name"
done
for system in controller b4 b3 b2 b1; do
  [ -d "$RUN_DIR/$system" ] || continue
  mkdir -p "$PKG_ROOT/run/$system"
  for name in report.json results.md; do
    [ -f "$RUN_DIR/$system/$name" ] && cp "$RUN_DIR/$system/$name" "$PKG_ROOT/run/$system/$name"
  done
done

cat > "$PKG_ROOT/EXCLUDED_RAW_ARTIFACTS.md" <<'EOF'
# Raw artifacts intentionally excluded

This public review package contains aggregate reports and provenance only.
Conversation-bearing answers, judgments, prompts, action logs, provider logs,
caches, and LongMemEval range files are excluded because they may contain
third-party benchmark text or local execution details. Their hashes and counts
remain in the sanitized manifests where available.
EOF

# Sanitize JSON/Markdown copies: remove local absolute paths and any accidental
# credential-shaped strings before checksumming or archiving.
"$PYTHON" - "$PKG_ROOT" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
secret = re.compile(r"(?:sk-or-v1-|sk-)[A-Za-z0-9_-]{20,}")
local_path = re.compile(r"/(?:Users|home)/[^\s\"']+")

def scrub(value):
    if isinstance(value, dict):
        return {
            key: scrub(child)
            for key, child in value.items()
            if not key.endswith("_path_local_not_redistributed")
        }
    if isinstance(value, list):
        return [scrub(child) for child in value]
    if isinstance(value, str):
        value = secret.sub("<secret-redacted>", value)
        return local_path.sub("<local-path-redacted>", value)
    return value

for path in root.rglob("*"):
    if not path.is_file():
        continue
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(
            json.dumps(scrub(payload), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    elif path.suffix in {".md", ".txt"}:
        text = path.read_text(encoding="utf-8", errors="strict")
        text = secret.sub("<secret-redacted>", text)
        text = local_path.sub("<local-path-redacted>", text)
        path.write_text(text, encoding="utf-8")
PY

# --- 2. environment report (no secret values) -------------------------- #
ENV_REPORT="$PKG_ROOT/ENV_REPORT.txt"
{
  echo "generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "run_id: $RUN_ID"
  echo "python: $($PYTHON --version 2>&1)"
  echo "git_head: $(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo 'not-a-git-repo')"
  echo "frozen_config: configs/release/final.yaml"
  echo "freeze_hashes: artifacts/manifests/freeze_hashes.json"
  echo "key_presence (values NEVER shown):"
  if [ -n "${OPENROUTER_API_KEY:-}" ]; then echo "  OPENROUTER_API_KEY: SET"; else echo "  OPENROUTER_API_KEY: not-set"; fi
} > "$ENV_REPORT"
echo "[package] wrote $ENV_REPORT"

# --- 3. include the freeze manifest + protocol pointers ---------------- #
mkdir -p "$PKG_ROOT/freeze"
[ -f artifacts/manifests/freeze_hashes.json ] && cp artifacts/manifests/freeze_hashes.json "$PKG_ROOT/freeze/"
[ -f configs/release/final.yaml ] && cp configs/release/final.yaml "$PKG_ROOT/freeze/"
[ -f "$PKG_ROOT/run/manifest.json" ] && cp "$PKG_ROOT/run/manifest.json" "$PKG_ROOT/run_manifest.json" || true

# Fail closed if sanitization missed a credential or local home path.
"$PYTHON" - "$PKG_ROOT" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
pattern = re.compile(rb"(?:sk-or-v1-|sk-)[A-Za-z0-9_-]{20,}|/(?:Users|home)/[^\s]+")
bad = []
for path in root.rglob("*"):
    if path.is_file() and pattern.search(path.read_bytes()):
        bad.append(str(path.relative_to(root)))
if bad:
    raise SystemExit(f"[package] sensitive content remained: {bad}")
PY

# --- 4. checksums over everything in the package ----------------------- #
CHECKSUMS="$PKG_ROOT/CHECKSUMS.sha256"
( cd "$PKG_ROOT" && find . -type f ! -name CHECKSUMS.sha256 | LC_ALL=C sort \
    | while IFS= read -r f; do SHA "$f"; done ) > "$CHECKSUMS"
echo "[package] wrote $CHECKSUMS ($(wc -l < "$CHECKSUMS" | tr -d ' ') files)"

# --- 5. tar it up ------------------------------------------------------- #
OUT_TAR="$REPO/return_package_$RUN_ID.tar.gz"
( cd "$STAGE" && tar -czf "$OUT_TAR" "return_package_$RUN_ID" )
rm -rf "$STAGE"
echo "[package] wrote $OUT_TAR"
echo "[package] return this single file for review."
