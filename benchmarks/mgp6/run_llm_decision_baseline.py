#!/usr/bin/env python3
"""Zero-shot / few-shot LLM DECISION baselines for MGP-6 v2.

Unlike run_llm_controller.py (which carries engineered rule hints in its
system prompt), these baselines ask a plain LLM for the write action with
neutral action definitions and NO governance heuristics:

    zero  neutral action definitions only
    few   neutral definitions + K balanced exemplars from the TRAIN split
          (exemplar scenario_ids are excluded from evaluation)

To isolate DECISION quality, the committed memory state and the answer are
built deterministically from the predicted action with the same shared
builders every other system uses (systems/policies.py). The candidate value
comes from the shared closed-book extractor, not from the LLM.

Resumable and concurrent (same pattern as run_llm_controller.py).

Env:
    OPENROUTER_API_KEY   required (or OPENAI_API_KEY)
    MGP6_MODEL           default "qwen/qwen3.5-9b"
    MGP6_BASE_URL        default "https://openrouter.ai/api/v1"
    MGP6_CONCURRENCY     default 12

Usage:
    python3 run_llm_decision_baseline.py --mode zero \
        --out runs/llm_decision_zero/controller
    python3 run_llm_decision_baseline.py --mode few --shots 6 \
        --out runs/llm_decision_few6/controller
Then score:
    python3 metrics_mgp6.py --gold data/mgp6_v2.jsonl \
        --pred runs/llm_decision_zero/controller/predictions.jsonl \
        --bootstrap 1000 > runs/llm_decision_zero/controller/report.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from systems.extractor import Evidence, read_evidence  # noqa: E402
from systems.policies import (  # noqa: E402
    _answer,
    _keep_with_override,
    _prior_state,
    _superseded_state,
)

MODEL = os.environ.get("MGP6_MODEL", "qwen/qwen3.5-9b")
BASE_URL = os.environ.get("MGP6_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
CONCURRENCY = int(os.environ.get("MGP6_CONCURRENCY", "12"))

# Deliberately NEUTRAL: no provenance/temporal-scope/atomicity heuristics.
DECISION_SYSTEM = """You maintain a personal assistant's long-term memory. \
You are given the user's earlier dialogue, the currently stored memory, and \
ONE new event. Decide what to do with the stored value for the slot in \
question.

Actions:
- SUPERSEDE: replace the stored value with a new value from the new event.
- KEEP: leave the stored value as the authoritative value.
- ABSTAIN: make no commitment to memory.

Return ONLY compact JSON: {"action":"SUPERSEDE|KEEP|ABSTAIN"}"""


def _post(payload: dict[str, Any], retries: int = 4) -> str:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    last = ""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"].get("content")
            if content:
                return content.strip()
            last = "empty content"
        except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
            last = str(exc)
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"LLM call failed after {retries} tries: {last}")


def _chat(messages: list[dict[str, str]], max_tokens: int = 60) -> str:
    return _post(
        {
            "model": MODEL,
            "reasoning": {"enabled": False},
            "temperature": 0,
            "max_tokens": max_tokens,
            "messages": messages,
        }
    )


def _parse_action(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            action = str(json.loads(text[start : end + 1]).get("action", "")).upper()
            if action in ("KEEP", "SUPERSEDE", "ABSTAIN"):
                return action
        except json.JSONDecodeError:
            pass
    upper = text.upper()
    for action in ("SUPERSEDE", "ABSTAIN", "KEEP"):
        if action in upper:
            return action
    return "ABSTAIN"


def _state_lines(state: list[dict[str, Any]]) -> str:
    out = [
        f"- [{r.get('type')}] {r.get('text')} (confidence {r.get('confidence')})"
        for r in state
        if r.get("status") == "active"
    ]
    return "\n".join(out) or "- (empty)"


def _scenario_user_msg(scenario: dict[str, Any]) -> str:
    prefix = "\n".join(
        f"{m.get('role')}: {m.get('content')}" for m in scenario.get("base_dialogue_prefix", [])
    )
    prior = _state_lines(scenario.get("initial_memory_state", []))
    return (
        f"Earlier dialogue:\n{prefix or '(none)'}\n\n"
        f"Current memory (active records):\n{prior}\n\n"
        f"New event:\n{scenario.get('perturbation_event', '')}"
    )


def pick_exemplars(rows: list[dict[str, Any]], shots: int, seed: int) -> list[dict[str, Any]]:
    """Balanced exemplars from the train split, deterministic."""
    rng = random.Random(seed)
    train = [r for r in rows if r.get("split") == "train"]
    by_action: dict[str, list[dict[str, Any]]] = {}
    for r in train:
        by_action.setdefault(r["gold_action"], []).append(r)
    per = max(1, shots // 3)
    exemplars: list[dict[str, Any]] = []
    for action in ("KEEP", "SUPERSEDE", "ABSTAIN"):
        pool = sorted(by_action.get(action, []), key=lambda r: r["scenario_id"])
        rng.shuffle(pool)
        exemplars.extend(pool[:per])
    rng.shuffle(exemplars)
    return exemplars[:shots] if shots < len(exemplars) else exemplars


def build_messages(
    scenario: dict[str, Any], exemplars: list[dict[str, Any]]
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": DECISION_SYSTEM}]
    for ex in exemplars:
        messages.append({"role": "user", "content": _scenario_user_msg(ex)})
        messages.append({"role": "assistant", "content": json.dumps({"action": ex["gold_action"]})})
    messages.append({"role": "user", "content": _scenario_user_msg(scenario)})
    return messages


def predict(scenario: dict[str, Any], exemplars: list[dict[str, Any]]) -> dict[str, Any]:
    ev: Evidence | None = read_evidence(scenario)
    action = _parse_action(_chat(build_messages(scenario, exemplars)))

    slot = (
        ev.slot
        if ev
        else (scenario.get("initial_memory_state") or [{}])[0].get("semantic_slot", "")
    )
    if ev is None:
        state: list[dict[str, Any]] = _prior_state(scenario)
    elif action == "SUPERSEDE" and ev.has_candidate:
        state = _superseded_state(scenario, ev, ev.candidate_value)
    elif action == "SUPERSEDE":
        action = "ABSTAIN"  # cannot supersede without a candidate value
        state = _prior_state(scenario)
    elif action == "KEEP" and ev.temporary_clear and ev.has_candidate:
        state = _keep_with_override(scenario, ev, ev.candidate_value)
    else:
        state = _prior_state(scenario)

    return {
        "scenario_id": scenario["scenario_id"],
        "predicted_action": action,
        "predicted_memory_state": state,
        "predicted_answer": _answer(scenario, state, slot),
        "confidence": 0.5,
    }


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for line in path.open(encoding="utf-8"):
        if line.strip():
            try:
                ids.add(json.loads(line)["scenario_id"])
            except (json.JSONDecodeError, KeyError):
                pass
    return ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=HERE / "data" / "mgp6_v2.jsonl")
    parser.add_argument("--mode", choices=("zero", "few"), default="zero")
    parser.add_argument(
        "--shots", type=int, default=6, help="few-shot exemplar count (balanced over actions)"
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--split", default="", help="optional: train|dev|test")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    if not API_KEY:
        raise SystemExit("set OPENROUTER_API_KEY (or OPENAI_API_KEY)")

    out = args.out or (HERE / "runs" / f"llm_decision_{args.mode}" / "controller")
    out.mkdir(parents=True, exist_ok=True)
    pred_path = out / "predictions.jsonl"

    rows = load_scenarios(args.gold)
    exemplars = pick_exemplars(rows, args.shots, args.seed) if args.mode == "few" else []
    exemplar_ids = {e["scenario_id"] for e in exemplars}

    scenarios = rows
    if args.split:
        scenarios = [s for s in scenarios if s.get("split") == args.split]
    scenarios = [s for s in scenarios if s["scenario_id"] not in exemplar_ids]

    have = done_ids(pred_path)
    todo = [s for s in scenarios if s["scenario_id"] not in have]
    if args.limit > 0:
        todo = todo[: args.limit]

    meta = {
        "mode": args.mode,
        "model": MODEL,
        "shots": len(exemplars),
        "exemplar_ids": sorted(exemplar_ids),
        "seed": args.seed,
        "split": args.split or "all",
        "n_eval": len(scenarios),
    }
    (out / "baseline_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(
        f"[decision-{args.mode}] model={MODEL} shots={len(exemplars)} "
        f"done={len(have)} todo_now={len(todo)} total={len(scenarios)}"
    )
    if not todo:
        print("[decision] nothing to do (corpus complete for this split)")
        return 0

    lock = Lock()
    written = errors = 0
    with (
        pred_path.open("a", encoding="utf-8") as handle,
        ThreadPoolExecutor(max_workers=CONCURRENCY) as pool,
    ):
        futures = {pool.submit(predict, s, exemplars): s["scenario_id"] for s in todo}
        for fut in as_completed(futures):
            sid = futures[fut]
            try:
                row = fut.result()
            except Exception as exc:  # noqa: BLE001 - resume later
                errors += 1
                print(f"[decision] ERROR {sid}: {exc}", file=sys.stderr)
                continue
            with lock:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                written += 1
                if written % 20 == 0:
                    print(f"[decision] wrote {written}/{len(todo)}")

    print(f"[decision] wrote {written} rows ({errors} errors) -> {pred_path}")
    print(f"[decision] total now: {len(done_ids(pred_path))}/{len(scenarios)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
