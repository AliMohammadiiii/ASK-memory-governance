#!/usr/bin/env bash
# Ablations: (1) MGP-6 controller ablations rescore/verify from existing
# predictions (offline), and (2) the SSP correction ablation matrix, which is a
# PENDING placeholder because the correction code is PROPOSED only.
#
# MGP-6 ablation predictions live in the READ-ONLY archive ../artifacts/mgp6_v2/ablations/.
# Reports are written ONLY under runs_local/ (never into the archive).
#
# Usage:
#   bash scripts/experiments/run_ablations.sh --mgp6      # rescore MGP-6 ablations
#   bash scripts/experiments/run_ablations.sh --ssp       # SSP matrix status (pending)
#   bash scripts/experiments/run_ablations.sh --all       # both (default)
#   bash scripts/experiments/run_ablations.sh --dry-run
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

DO_MGP6=1; DO_SSP=1; DRY=0
if [ "$#" -gt 0 ]; then
  DO_MGP6=0; DO_SSP=0
  for arg in "$@"; do
    case "$arg" in
      --mgp6) DO_MGP6=1 ;;
      --ssp) DO_SSP=1 ;;
      --all) DO_MGP6=1; DO_SSP=1 ;;
      --dry-run) DRY=1 ;;
      *) echo "[ablations] unknown arg: $arg" >&2; exit 2 ;;
    esac
  done
  # if only --dry-run was given, default to both
  if [ "$DO_MGP6" -eq 0 ] && [ "$DO_SSP" -eq 0 ]; then DO_MGP6=1; DO_SSP=1; fi
fi

echo "[ablations] scorer   : $SCORER (offline; no models)"
echo "[ablations] archive  : $MGP6_ROOT (READ-ONLY)"
echo "[ablations] mgp6=$DO_MGP6 ssp=$DO_SSP dry_run=$DRY"

if [ "$DO_MGP6" -eq 1 ]; then
  OUT="runs_local/mgp6_ablations"
  ABL="full no_abstain no_lineage no_provenance no_typing"
  if [ -d "$OUT" ] && [ -n "$(ls -A "$OUT" 2>/dev/null)" ] && [ "$DRY" -eq 0 ]; then
    echo "[ablations] ERROR: '$OUT' exists and is non-empty; refusing to overwrite." >&2
    exit 1
  fi
  for a in $ABL; do
    pred="$MGP6_ROOT/runs/ablations/$a/report.json"
    predfile="$MGP6_ROOT/runs/ablations/$a/predictions.jsonl"
    if [ ! -f "$predfile" ]; then
      echo "[ablations] SKIP $a: no predictions at $predfile"
      continue
    fi
    n="$(wc -l < "$predfile" | tr -d ' ')"
    echo "[ablations] MGP-6 ablation '$a' (predictions=$n)"
    if [ "$DRY" -eq 1 ]; then
      echo "[ablations]   would write $OUT/${a}_report.json"
      continue
    fi
    mkdir -p "$OUT"
    tmp="$OUT/${a}_report.json.tmp"
    if "$PYTHON" "$SCORER" --gold "$GOLD" --pred "$predfile" --bootstrap "$BOOTSTRAP" > "$tmp"; then
      mv "$tmp" "$OUT/${a}_report.json"
      "$PYTHON" - "$OUT/${a}_report.json" "$a" <<'PY'
import json, sys
r = json.load(open(sys.argv[1])); a = sys.argv[2]
f = r.get("full", {})
print(f"[ablations]   {a}: action_accuracy={f.get('action_accuracy',{}).get('value')} "
      f"macro_f1={f.get('macro_f1',{}).get('value')} "
      f"lineage={f.get('lineage_correctness',{}).get('value')}")
PY
    else
      rm -f "$tmp"; echo "[ablations]   ERROR scoring $a" >&2
    fi
  done
  echo "[ablations] MGP-6 ablation rescore complete -> $OUT (compare to ledger ablation/* rows)"
fi

if [ "$DO_SSP" -eq 1 ]; then
  echo "[ablations] ================= SSP ABLATION MATRIX (PENDING) ================="
  echo "[ablations] Arms A..G are specified in docs/research/SINGLE_SESSION_PREFERENCE_METHOD.md"
  echo "[ablations] and enumerated in FINAL_RUN_MATRIX.yaml (ssp_ablation_*)."
  echo "[ablations]"
  echo "[ablations]   Arm A (baseline)                      : diagnostic v7 reference 11/30"
  echo "[ablations]   Arms B,C,D,E,F,G                       : INCOMPLETE (design not implemented)"
  echo "[ablations]"
  echo "[ablations] Arms B-G require the PROPOSED correction code (typed preference"
  echo "[ablations] record + provenance-constrained retrieval + answer contract), which"
  echo "[ablations] is DESIGN-ONLY and NOT implemented. No SSP-improvement claim may be"
  echo "[ablations] made until these arms are implemented and run on hosted models"
  echo "[ablations] (OPENROUTER_API_KEY + LongMemEval data), paired by item vs arm A,"
  echo "[ablations] with McNemar + Holm per FINAL_ANALYSIS_PLAN.md sec 4c."
  OUT="runs_local/ssp_ablation"
  if [ "$DRY" -eq 0 ]; then
    mkdir -p "$OUT"
    tmp="$OUT/STATUS.json.tmp"
    cat > "$tmp" <<'JSON'
{
  "matrix": "SSP correction ablation (method doc sec 4)",
  "baseline_arm_A": {"status": "diagnostic_only", "v7_reference": "11/30",
                     "topup_observed": "8/29, one unresolved; maximum 9/30"},
  "arms_B_to_G": {"status": "incomplete",
                  "reason": "PROPOSED correction code not implemented"},
  "prereqs": ["newly authorized OPENROUTER_API_KEY", "LongMemEval-M data local"]
}
JSON
    mv "$tmp" "$OUT/STATUS.json"
    echo "[ablations] wrote $OUT/STATUS.json"
  fi
fi
