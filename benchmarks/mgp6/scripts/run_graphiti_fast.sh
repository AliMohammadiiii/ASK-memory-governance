#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-smoke}"

export PYTHONUNBUFFERED=1

export GRAPHITI_FALKORDB_HOST="${GRAPHITI_FALKORDB_HOST:-127.0.0.1}"
export GRAPHITI_FALKORDB_PORT="${GRAPHITI_FALKORDB_PORT:-6379}"

export GRAPHITI_EMBED_URL="${GRAPHITI_EMBED_URL:-http://127.0.0.1:8100/v1}"
export GRAPHITI_EMBED_MODEL="${GRAPHITI_EMBED_MODEL:-sentence-transformers/all-MiniLM-L6-v2}"
export GRAPHITI_EMBED_DIM="${GRAPHITI_EMBED_DIM:-384}"

# Start conservative. Try 8 later if Modal stays stable.
export GRAPHITI_MAX_COROUTINES="${GRAPHITI_MAX_COROUTINES:-4}"
export SEMAPHORE_LIMIT="${SEMAPHORE_LIMIT:-4}"

# Graphiti retries individual extraction calls, but a provider can still return
# an empty response for a whole scenario.  The Python runner records completed
# scenarios and skips them on later invocations, so full runs can safely make
# bounded resume passes until every gold scenario has a raw result.
export GRAPHITI_MAX_PASSES="${GRAPHITI_MAX_PASSES:-12}"
export GRAPHITI_RESUME_DELAY="${GRAPHITI_RESUME_DELAY:-15}"

# Set GRAPHITI_PYTHON when Graphiti is installed in a dedicated virtualenv.
PYTHON_BIN="${GRAPHITI_PYTHON:-python3}"

GOLD="data/mgp6_v2.jsonl"
EXPECTED_SCENARIOS="$(wc -l < "${GOLD}" | tr -d '[:space:]')"

completed_scenarios() {
  local raw_path="$1/raw_results.jsonl"

  if [ ! -f "${raw_path}" ]; then
    echo 0
    return
  fi

  "${PYTHON_BIN}" -c '
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    print(len({json.loads(line)["scenario_id"] for line in handle if line.strip()}))
' "${raw_path}"
}

run_full_to_completion() {
  local out="$1"
  local pass completed

  for pass in $(seq 1 "${GRAPHITI_MAX_PASSES}"); do
    completed="$(completed_scenarios "${out}")"
    if [ "${completed}" -eq "${EXPECTED_SCENARIOS}" ]; then
      echo "==> Graphiti full run already complete: ${completed}/${EXPECTED_SCENARIOS}"
      return 0
    fi

    echo "==> Graphiti full pass ${pass}/${GRAPHITI_MAX_PASSES}: ${completed}/${EXPECTED_SCENARIOS} complete"
    time "${PYTHON_BIN}" external/run_graphiti.py --out "${out}"

    completed="$(completed_scenarios "${out}")"
    if [ "${completed}" -eq "${EXPECTED_SCENARIOS}" ]; then
      echo "==> Graphiti full run complete: ${completed}/${EXPECTED_SCENARIOS}"
      return 0
    fi

    if [ "${pass}" -lt "${GRAPHITI_MAX_PASSES}" ]; then
      echo "==> ${completed}/${EXPECTED_SCENARIOS} complete; retrying missing scenarios in ${GRAPHITI_RESUME_DELAY}s"
      sleep "${GRAPHITI_RESUME_DELAY}"
    fi
  done

  echo "ERROR: Graphiti full run incomplete after ${GRAPHITI_MAX_PASSES} passes: ${completed}/${EXPECTED_SCENARIOS}" >&2
  return 1
}

echo "==> Checking FalkorDB Docker container"

if ! docker inspect mgp6-falkordb >/dev/null 2>&1; then
  echo "ERROR: container mgp6-falkordb does not exist"
  exit 1
fi

if [ "$(docker inspect -f '{{.State.Running}}' mgp6-falkordb)" != "true" ]; then
  docker start mgp6-falkordb >/dev/null
fi

for i in $(seq 1 30); do
  if docker exec mgp6-falkordb redis-cli PING 2>/dev/null | grep -q PONG; then
    break
  fi

  if [ "$i" -eq 30 ]; then
    echo "ERROR: FalkorDB did not become ready"
    exit 1
  fi

  sleep 1
done

echo "==> FalkorDB: OK"

echo "==> Checking local embedding endpoint"

curl -fsS \
  -X POST \
  "${GRAPHITI_EMBED_URL}/embeddings" \
  -H 'Content-Type: application/json' \
  -d "{
    \"model\": \"${GRAPHITI_EMBED_MODEL}\",
    \"input\": \"graphiti health check\"
  }" \
  >/dev/null

echo "==> Embeddings: OK"

"${PYTHON_BIN}" -m py_compile external/run_graphiti.py

echo "==> run_graphiti.py: syntax OK"
echo "==> max_coroutines=${GRAPHITI_MAX_COROUTINES}"

case "$MODE" in
  fresh-smoke)
    export GRAPHITI_FALKORDB_DATABASE="mgp6_graphiti_smoke"
    rm -rf runs/ext_graphiti_smoke/controller

    time "${PYTHON_BIN}" external/run_graphiti.py \
      --limit 2 \
      --out runs/ext_graphiti_smoke/controller
    ;;

  smoke)
    export GRAPHITI_FALKORDB_DATABASE="mgp6_graphiti_smoke"

    time "${PYTHON_BIN}" external/run_graphiti.py \
      --limit 2 \
      --out runs/ext_graphiti_smoke/controller
    ;;

  fresh-full)
    export GRAPHITI_FALKORDB_DATABASE="mgp6_graphiti_full"
    rm -rf runs/ext_graphiti/controller

    run_full_to_completion runs/ext_graphiti/controller
    ;;

  full)
    export GRAPHITI_FALKORDB_DATABASE="mgp6_graphiti_full"

    run_full_to_completion runs/ext_graphiti/controller
    ;;

  *)
    echo "Usage:"
    echo "  $0 fresh-smoke"
    echo "  $0 smoke"
    echo "  $0 fresh-full"
    echo "  $0 full"
    exit 2
    ;;
esac
