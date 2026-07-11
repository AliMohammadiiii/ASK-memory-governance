#!/usr/bin/env bash
# Cross-model sweep on MGP-6 v2: run the LLM controller (and optionally the
# zero-shot decision baseline) with several backbones, score each, and write
# an aggregate comparison. Shows the commitment/state/answer gap is not an
# artifact of one model.
#
# Prereq: export OPENROUTER_API_KEY=... before running.
#
# Usage:
#   bash run_model_sweep.sh
#   MODELS="qwen/qwen3.5-9b google/gemma-4-31b-it qwen/qwen3.5-35b-a3b" \
#       WITH_DECISION=1 bash run_model_sweep.sh
#
# Env overrides:
#   MODELS         space-separated OpenRouter model ids
#   OUT_ROOT       default runs/model_sweep
#   BOOTSTRAP      default 1000
#   WITH_DECISION  1 = also run the zero-shot decision baseline per model
set -euo pipefail
cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

: "${OPENROUTER_API_KEY:?export OPENROUTER_API_KEY before running}"

PYTHON="${PYTHON:-python3}"
GOLD="${GOLD:-data/mgp6_v2.jsonl}"
OUT_ROOT="${OUT_ROOT:-runs/model_sweep}"
BOOTSTRAP="${BOOTSTRAP:-1000}"
WITH_DECISION="${WITH_DECISION:-0}"
MODELS="${MODELS:-qwen/qwen3.5-9b google/gemma-4-31b-it qwen/qwen3.5-35b-a3b}"

slug() { echo "$1" | tr '/.:' '___' ; }

for MODEL in ${MODELS}; do
  TAG="$(slug "${MODEL}")"
  OUT="${OUT_ROOT}/${TAG}/controller"
  echo "=== [sweep] model=${MODEL} -> ${OUT}"
  mkdir -p "${OUT}"

  # resumable loop until the corpus is complete for this model
  for i in 1 2 3 4 5; do
    MGP6_MODEL="${MODEL}" "${PYTHON}" run_llm_controller.py \
      --gold "${GOLD}" --out "${OUT}" || true
    N="$(wc -l < "${OUT}/predictions.jsonl" 2>/dev/null || echo 0)"
    TOTAL="$(wc -l < "${GOLD}")"
    echo "[sweep] ${MODEL}: ${N}/${TOTAL} predictions"
    [ "${N}" -ge "${TOTAL}" ] && break
    sleep 5
  done

  "${PYTHON}" metrics_mgp6.py --gold "${GOLD}" \
    --pred "${OUT}/predictions.jsonl" --bootstrap "${BOOTSTRAP}" \
    > "${OUT}/report.json"
  echo "[sweep] scored -> ${OUT}/report.json"

  if [ "${WITH_DECISION}" = "1" ]; then
    DOUT="${OUT_ROOT}/${TAG}/decision_zero"
    mkdir -p "${DOUT}"
    for i in 1 2 3 4 5; do
      MGP6_MODEL="${MODEL}" "${PYTHON}" run_llm_decision_baseline.py \
        --mode zero --gold "${GOLD}" --out "${DOUT}" || true
      N="$(wc -l < "${DOUT}/predictions.jsonl" 2>/dev/null || echo 0)"
      [ "${N}" -ge "$(wc -l < "${GOLD}")" ] && break
      sleep 5
    done
    "${PYTHON}" metrics_mgp6.py --gold "${GOLD}" \
      --pred "${DOUT}/predictions.jsonl" --bootstrap "${BOOTSTRAP}" \
      > "${DOUT}/report.json"
    echo "[sweep] decision baseline scored -> ${DOUT}/report.json"
  fi
done

# aggregate
"${PYTHON}" - "$OUT_ROOT" <<'PY'
import json, sys
from pathlib import Path

root = Path(sys.argv[1])
keys = ("action_accuracy", "macro_f1", "artifact_semantic_accuracy",
        "lineage_correctness", "invalid_commit_rate",
        "fama_presence_absence_conjunction", "premise_resistance_rate")

def point(node):
    return node.get("value") if isinstance(node, dict) else node

table = {}
for report in sorted(root.glob("*/*/report.json")):
    tag = f"{report.parent.parent.name}/{report.parent.name}"
    full = json.loads(report.read_text())["full"]
    table[tag] = {k: point(full.get(k)) for k in keys}

out = root / "sweep_summary.json"
out.write_text(json.dumps(table, indent=2, sort_keys=True))
print(f"[sweep] summary -> {out}\n")
header = f"{'model/system':<45}" + "".join(f"{k[:16]:>18}" for k in keys)
print(header)
for tag, row in sorted(table.items()):
    cells = "".join(f"{v:>18.3f}" if isinstance(v, (int, float)) else f"{'-':>18}"
                    for v in (row[k] for k in keys))
    print(f"{tag:<45}" + cells)
PY

echo "[sweep] done."
