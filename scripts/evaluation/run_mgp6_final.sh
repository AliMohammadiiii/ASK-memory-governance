#!/usr/bin/env bash
# Rescore / verify the MGP-6 v2 final tables from EXISTING predictions, and
# recompute the few-shot (6-shot) decision baseline whose report.json is 0 bytes.
#
# MGP-6 final numbers are already LOCKED in artifacts/results_ledger.json; this
# script reproduces them from the archived per-item predictions using the SAME
# scorer (benchmarks/mgp6/metrics_mgp6.py). It is offline (no models, no network).
#
# Reads predictions from the READ-ONLY archive ../artifacts/mgp6_v2/... and writes
# reports ONLY under runs_local/ (never into the archive).
#
# Usage:
#   bash scripts/evaluation/run_mgp6_final.sh --few6      # just the few6 rescore
#   bash scripts/evaluation/run_mgp6_final.sh --full      # few6 + verify all locked rows
#   bash scripts/evaluation/run_mgp6_final.sh --dry-run   # print plan only
#
# macOS-compatible; python3 only.
set -euo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
cd "$REPO"

PYTHON="${PYTHON:-python3}"
if [ -x .venv/bin/python ]; then PYTHON=".venv/bin/python"; fi

MGP6_ROOT="${MGP6_ROOT:-$REPO/../mgp6_v2}"
GOLD="benchmarks/mgp6/data/mgp6_v2.jsonl"
SCORER="benchmarks/mgp6/metrics_mgp6.py"
BOOTSTRAP="${BOOTSTRAP:-1000}"

MODE="--full"
DRY=0
for arg in "$@"; do
  case "$arg" in
    --few6) MODE="--few6" ;;
    --full) MODE="--full" ;;
    --dry-run) DRY=1 ;;
    *) echo "[mgp6-final] unknown arg: $arg" >&2; exit 2 ;;
  esac
done

echo "[mgp6-final] scorer      : $SCORER"
echo "[mgp6-final] gold        : $GOLD"
echo "[mgp6-final] archive root: $MGP6_ROOT (READ-ONLY)"
echo "[mgp6-final] bootstrap   : $BOOTSTRAP"
echo "[mgp6-final] models      : none (offline rescore of existing predictions)"
echo "[mgp6-final] mode        : $MODE"

if [ ! -f "$GOLD" ]; then echo "[mgp6-final] ERROR: missing gold $GOLD" >&2; exit 1; fi
if [ ! -d "$MGP6_ROOT" ]; then
  echo "[mgp6-final] ERROR: archive $MGP6_ROOT not found (expected sibling of repo)." >&2
  exit 1
fi

# system alias -> predictions path (relative to MGP6_ROOT)
# Only rows the ledger marks final_candidate* (plus few6 pending) are rescored.
SYS_NAMES="b1 b2 b3 b4 controller_rule llm_controller zero_shot few6"
pred_path() {
  case "$1" in
    b1)             echo "runs/ref_5systems/b1/predictions.jsonl" ;;
    b2)             echo "runs/ref_5systems/b2/predictions.jsonl" ;;
    b3)             echo "runs/ref_5systems/b3/predictions.jsonl" ;;
    b4)             echo "runs/ref_5systems/b4/predictions.jsonl" ;;
    controller_rule)echo "runs/ref_5systems/controller/predictions.jsonl" ;;
    llm_controller) echo "runs/llm_qwen35_9b/controller/predictions.jsonl" ;;
    zero_shot)      echo "runs/llm_decision_zero/controller/predictions.jsonl" ;;
    few6)           echo "runs/llm_decision_few6/controller/predictions.jsonl" ;;
    *) echo "" ;;
  esac
}

OUT_ROOT="runs_local/mgp6_verify"
FEW6_OUT="runs_local/mgp6_few6_rescore"

# Immutability: refuse to clobber a non-empty final output dir unless dry-run.
guard_dir() {
  local d="$1"
  if [ -d "$d" ] && [ -n "$(ls -A "$d" 2>/dev/null)" ]; then
    echo "[mgp6-final] ERROR: final output dir '$d' exists and is non-empty." >&2
    echo "[mgp6-final] Refusing to overwrite. Move/remove it or pick a new run id." >&2
    exit 1
  fi
}

rescore_one() {
  local sys="$1" out_dir="$2"
  local rel; rel="$(pred_path "$sys")"
  local pred="$MGP6_ROOT/$rel"
  if [ ! -f "$pred" ]; then
    echo "[mgp6-final] SKIP $sys: predictions not found ($pred)"
    return 0
  fi
  local n; n="$(wc -l < "$pred" | tr -d ' ')"
  echo "[mgp6-final] rescore $sys  (predictions=$n)  <- $rel"
  if [ "$DRY" -eq 1 ]; then
    echo "[mgp6-final]   would write $out_dir/${sys}_report.json"
    return 0
  fi
  mkdir -p "$out_dir"
  local tmp="$out_dir/${sys}_report.json.tmp"
  local final="$out_dir/${sys}_report.json"
  if "$PYTHON" "$SCORER" --gold "$GOLD" --pred "$pred" --bootstrap "$BOOTSTRAP" > "$tmp"; then
    mv "$tmp" "$final"
    "$PYTHON" - "$final" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
f = r.get("full", {})
acc = f.get("action_accuracy", {}).get("value")
mf1 = f.get("macro_f1", {}).get("value")
print(f"[mgp6-final]   action_accuracy={acc}  macro_f1={mf1}")
PY
  else
    rm -f "$tmp"
    echo "[mgp6-final]   ERROR scoring $sys" >&2
    return 1
  fi
}

if [ "$MODE" = "--few6" ]; then
  [ "$DRY" -eq 1 ] || guard_dir "$FEW6_OUT"
  rescore_one few6 "$FEW6_OUT"
  echo "[mgp6-final] few6 rescore complete -> $FEW6_OUT/few6_report.json"
  exit 0
fi

# --full: verify all locked rows, plus few6.
[ "$DRY" -eq 1 ] || guard_dir "$OUT_ROOT"
for sys in $SYS_NAMES; do
  if [ "$sys" = "few6" ]; then
    [ "$DRY" -eq 1 ] || guard_dir "$FEW6_OUT"
    rescore_one few6 "$FEW6_OUT"
  else
    rescore_one "$sys" "$OUT_ROOT"
  fi
done

echo "[mgp6-final] done. Compare against artifacts/results_ledger.json to confirm the locked values reproduce."
echo "[mgp6-final] Pre-specified paired significance (McNemar + Holm):"
echo "    $PYTHON scripts/analysis/mcnemar_mgp6.py --mgp6-root $MGP6_ROOT"
