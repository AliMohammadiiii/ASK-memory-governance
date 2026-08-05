#!/usr/bin/env python3
"""Real LLM-backed controller for MGP-6 v2 via an OpenAI-compatible endpoint.

Runs the closed-book two-stage protocol with a chat model (default OpenRouter
``qwen/qwen3.5-9b``). The scorer (``metrics_mgp6.py``) judges answers with
regexes, so *no* LLM judge is needed here.

The runner is **resumable** (skips scenario_ids already in the output file) and
**concurrent**, so it can be called repeatedly until the corpus is complete -
handy where background processes do not persist between shell calls.

Env:
    OPENROUTER_API_KEY   required (or OPENAI_API_KEY)
    MGP6_MODEL           default "qwen/qwen3.5-9b"
    MGP6_BASE_URL        default "https://openrouter.ai/api/v1"
    MGP6_ALLOW_INSECURE_HTTP  set to "1" only for a controlled remote HTTP endpoint
    MGP6_CONCURRENCY     default 12

Usage:
    python3 run_llm_controller.py --gold data/mgp6_v2.jsonl \
        --out runs/llm_qwen35_9b/controller --limit 60
"""

from __future__ import annotations

import argparse
import json
import os
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
sys.path.insert(0, str(HERE.parents[1] / "src"))

from systems.extractor import Evidence, read_evidence  # noqa: E402
from systems.policies import (  # noqa: E402
    _keep_with_override,
    _prior_state,
    _superseded_state,
)

from ask.endpoints import validate_http_endpoint  # noqa: E402

MODEL = os.environ.get("MGP6_MODEL", "qwen/qwen3.5-9b")
BASE_URL = validate_http_endpoint(
    os.environ.get("MGP6_BASE_URL", "https://openrouter.ai/api/v1"),
    allow_insecure_http=os.environ.get("MGP6_ALLOW_INSECURE_HTTP") == "1",
).rstrip("/")
API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
CONCURRENCY = int(os.environ.get("MGP6_CONCURRENCY", "12"))

WRITE_SYSTEM = """You are a long-term memory controller. Given a user's prior \
memory state and ONE new event, decide the write action for the single \
semantic slot in question. You never see the later question.

Actions:
- SUPERSEDE: the new event is reliable, from the user, about the SAME slot, \
atomic, and states a durable replacement value. Replace with retained lineage.
- KEEP: the new event is only a clear TEMPORARY override (e.g. "just for \
tonight", "my usual still stands"). Keep the durable value unchanged.
- ABSTAIN: do NOT commit. Use when evidence is not from the user directly \
(unattributed quote, forum post, third party), is garbled/low-confidence, is a \
tool/assistant guess that the user never confirmed, or is a hedged/uncertain \
temporary candidate.

Return ONLY compact JSON:
{"action":"SUPERSEDE|KEEP|ABSTAIN","value":"<new slot value or null>","confidence":<0..1>}
For SUPERSEDE give the new durable value. For KEEP give the temporary value (or \
null). For ABSTAIN use null."""

ANSWER_SYSTEM = """You answer a user's question using ONLY the given ACTIVE \
memory. Prefer the durable (stable_pref / episodic_fact) active value; ignore \
temporary notes. If the question wrongly presupposes an old value, reject it \
and state the correct current value. Be concise (one sentence)."""


def _post(payload: dict[str, Any], retries: int = 4) -> str:
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    last = ""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            msg = body["choices"][0]["message"]
            content = msg.get("content")
            if content:
                return content.strip()
            last = "empty content"
        except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
            last = str(exc)
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"LLM call failed after {retries} tries: {last}")


def _chat(system: str, user: str, max_tokens: int) -> str:
    return _post(
        {
            "model": MODEL,
            "reasoning": {"enabled": False},
            "temperature": 0,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    )


def _parse_json(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def _state_lines(state: list[dict[str, Any]]) -> str:
    out = []
    for r in state:
        if r.get("status") == "active":
            out.append(f"- [{r.get('type')}] {r.get('text')} (confidence {r.get('confidence')})")
    return "\n".join(out) or "- (empty)"


def predict(scenario: dict[str, Any]) -> dict[str, Any]:
    ev: Evidence | None = read_evidence(scenario)
    prefix = "\n".join(
        f"{m.get('role')}: {m.get('content')}" for m in scenario.get("base_dialogue_prefix", [])
    )
    prior = _state_lines(scenario.get("initial_memory_state", []))
    slot = ev.slot if ev else scenario.get("initial_memory_state", [{}])[0].get("semantic_slot", "")

    write_user = (
        f"Slot in question: {slot}\n\n"
        f"Earlier dialogue:\n{prefix or '(none)'}\n\n"
        f"Current memory (active records):\n{prior}\n\n"
        f"New event:\n{scenario.get('perturbation_event', '')}"
    )
    decision = _parse_json(_chat(WRITE_SYSTEM, write_user, 120))
    action = str(decision.get("action", "")).upper()
    if action not in ("KEEP", "SUPERSEDE", "ABSTAIN"):
        action = "ABSTAIN"
    value = decision.get("value")
    value = value.strip() if isinstance(value, str) and value.strip().lower() != "null" else None
    conf = decision.get("confidence")
    conf = float(conf) if isinstance(conf, (int, float)) and 0 <= conf <= 1 else 0.5

    # Build the committed state from the LLM action (reuse shared builders).
    if ev is None:
        state: list[dict[str, Any]] = []
    elif action == "SUPERSEDE" and value:
        state = _superseded_state(scenario, ev, value)
    elif action == "KEEP" and value:
        state = _keep_with_override(scenario, ev, value)
    else:
        if action == "SUPERSEDE" and not value:
            action = "ABSTAIN"  # cannot supersede without a value
        state = _prior_state(scenario)

    # Answer stage: reveal the query, answer from the committed active state.
    active = _state_lines(state)
    answer_user = f"ACTIVE memory:\n{active}\n\nQuestion: {scenario.get('evaluation_query', '')}"
    answer = _chat(ANSWER_SYSTEM, answer_user, 120)

    return {
        "scenario_id": scenario["scenario_id"],
        "predicted_action": action,
        "predicted_memory_state": state,
        "predicted_answer": answer,
        "confidence": round(conf, 3),
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
    parser.add_argument("--out", type=Path, default=HERE / "runs" / "llm_qwen35_9b" / "controller")
    parser.add_argument(
        "--limit", type=int, default=0, help="max NEW scenarios this call (0 = all)"
    )
    parser.add_argument("--split", default="", help="optional split filter: train|dev|test")
    args = parser.parse_args(argv)

    if not API_KEY:
        raise SystemExit("set OPENROUTER_API_KEY (or OPENAI_API_KEY)")

    args.out.mkdir(parents=True, exist_ok=True)
    pred_path = args.out / "predictions.jsonl"
    scenarios = load_scenarios(args.gold)
    if args.split:
        scenarios = [s for s in scenarios if s.get("split") == args.split]
    have = done_ids(pred_path)
    todo = [s for s in scenarios if s["scenario_id"] not in have]
    if args.limit > 0:
        todo = todo[: args.limit]

    print(f"[llm] model={MODEL} done={len(have)} todo_now={len(todo)} total={len(scenarios)}")
    if not todo:
        print("[llm] nothing to do (corpus complete for this split)")
        return 0

    lock = Lock()
    written = 0
    errors = 0
    with (
        pred_path.open("a", encoding="utf-8") as handle,
        ThreadPoolExecutor(max_workers=CONCURRENCY) as pool,
    ):
        futures = {pool.submit(predict, s): s["scenario_id"] for s in todo}
        for fut in as_completed(futures):
            sid = futures[fut]
            try:
                row = fut.result()
            except Exception as exc:  # noqa: BLE001 - keep going, resume later
                errors += 1
                print(f"[llm] ERROR {sid}: {exc}", file=sys.stderr)
                continue
            with lock:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                written += 1
                if written % 20 == 0:
                    print(f"[llm] wrote {written}/{len(todo)}")

    print(f"[llm] wrote {written} rows ({errors} errors) -> {pred_path}")
    print(f"[llm] total now: {len(done_ids(pred_path))}/{len(scenarios)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
