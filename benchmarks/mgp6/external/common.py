"""Shared framework for EXTERNAL memory-system baselines on MGP-6 v2.

External systems (Mem0, Zep/Graphiti, Letta, MemOS) do not expose the
KEEP/SUPERSEDE/ABSTAIN vocabulary, typed records, or supersession links.
Per the evaluation protocol, they are scored primarily on **action** (via a
documented observation->action mapping) and **answer** metrics; artifact and
lineage columns are reported as N/A in the paper.

Protocol per scenario (identical closed-book inputs as every other system):
  1. reset an ISOLATED store for the scenario;
  2. seed the prior memory records + earlier dialogue;
  3. feed the ONE perturbation event through the system's native write path;
  4. observe the store: did the new candidate value get committed? was the
     old value replaced/invalidated?
  5. answer the evaluation query from the system's native retrieval, using
     the SAME neutral answer prompt/model as the other LLM runners
     (adapters that answer natively, e.g. Letta agents, are flagged).

Observation -> action mapping (documented in the paper):
  - old value replaced/invalidated, or new value present and old absent
        -> SUPERSEDE
  - new value stored while the old also remains active
        -> INVALID_COMMIT, extras.dual_active = true
        The system committed conflicting state without completing a valid
        supersession transition. INVALID_COMMIT is a prediction-only outcome,
        never a gold MGP-6 action.
  - store unchanged (no commit)
        -> NOOP, exported under BOTH mappings:
             predictions.jsonl              NOOP -> KEEP   (default)
             predictions_noop_abstain.jsonl NOOP -> ABSTAIN
        Externals cannot express the KEEP-vs-ABSTAIN distinction; report
        both scores and cite the better one as the system's upper bound.

Outputs under --out:
    raw_results.jsonl               resumable per-scenario observations
    predictions.jsonl               metrics_mgp6-compatible (NOOP->KEEP)
    predictions_noop_abstain.jsonl  variant mapping (NOOP->ABSTAIN)
    adapter_meta.json               model/version/config provenance
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from systems.extractor import read_evidence  # noqa: E402

ANSWER_MODEL = os.environ.get("MGP6_MODEL", "qwen/qwen3.5-9b")
BASE_URL = os.environ.get("MGP6_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")

# Same neutral answer contract as run_llm_controller.py, for comparability.
ANSWER_SYSTEM = """You answer a user's question using ONLY the given memory \
snippets retrieved from a long-term memory system. Prefer the value that is \
currently true for the user; ignore clearly temporary notes. If the question \
wrongly presupposes an old value, reject it and state the correct current \
value. If the memory contains nothing relevant, say you do not have a stored \
value. Be concise (one sentence)."""


def chat(system: str, user: str, max_tokens: int = 120, retries: int = 4) -> str:
    payload = {
        "model": ANSWER_MODEL,
        "reasoning": {"enabled": False},
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    last = ""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=90) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"].get("content")
            if content:
                return content.strip()
            last = "empty content"
        except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
            last = str(exc)
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"answer LLM failed after {retries} tries: {last}")


class WriteObservation:
    """What the adapter could observe about its own write."""

    def __init__(self, replaced_old: bool = False, committed_new: bool = False, raw: Any = None):
        self.replaced_old = replaced_old
        self.committed_new = committed_new
        self.raw = raw


class ExternalAdapter(ABC):
    """One external memory system, driven through its NATIVE write path."""

    name: str = "external"
    answers_natively: bool = False  # e.g. Letta agents answer themselves

    @abstractmethod
    def reset(self, scenario_id: str) -> None: ...

    @abstractmethod
    def seed(self, records: list[dict[str, Any]], dialogue: list[dict[str, str]]) -> None:
        """Install prior memory records + earlier dialogue (ground truth)."""

    @abstractmethod
    def write(self, text: str) -> WriteObservation:
        """Feed the perturbation event through the native write path."""

    @abstractmethod
    def snapshot(self) -> list[str]:
        """All memory texts currently active in the store."""

    @abstractmethod
    def search(self, query: str, k: int = 5) -> list[str]:
        """Native retrieval for the answer stage."""

    def answer_natively(self, query: str) -> str | None:
        return None

    def close(self) -> None:
        pass

    def meta(self) -> dict[str, Any]:
        return {}


def _norm(s: str) -> str:
    return " ".join(str(s).lower().split())


def _contains(texts: list[str], value: str | None) -> bool:
    if not value:
        return False
    blob = _norm(" || ".join(texts))
    return _norm(value) in blob


def derive_action(
    prior_value: str | None,
    candidate_value: str | None,
    post_texts: list[str],
    obs: WriteObservation,
) -> tuple[str, dict[str, Any]]:
    new_in = _contains(post_texts, candidate_value)
    old_in = _contains(post_texts, prior_value)
    extras: dict[str, Any] = {
        "new_in_store": new_in,
        "old_in_store": old_in,
        "adapter_replaced": obs.replaced_old,
        "adapter_committed": obs.committed_new,
    }
    if obs.replaced_old or (new_in and not old_in):
        return "SUPERSEDE", extras
    if new_in and old_in:
        extras["dual_active"] = True
        extras["invalid_commit"] = True
        extras["invalid_commit_reason"] = "dual_active_conflict"
        return "INVALID_COMMIT", extras
    return "NOOP", extras


def state_records(scenario: dict[str, Any], texts: list[str]) -> list[dict[str, Any]]:
    slot = (scenario.get("initial_memory_state") or [{}])[0].get("semantic_slot")
    records = []
    for i, txt in enumerate(texts):
        records.append(
            {
                "id": f"{scenario['scenario_id'].lower()}-ext{i}",
                "type": "episodic_fact",
                "text": str(txt),
                "confidence": 0.5,
                "status": "active",
                "supersedes_id": None,
                "valid_from": "session_2",
                "semantic_slot": slot,
                "source": "external_store",
            }
        )
    return records


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out = set()
    for line in path.open(encoding="utf-8"):
        if line.strip():
            try:
                out.add(json.loads(line)["scenario_id"])
            except (json.JSONDecodeError, KeyError):
                pass
    return out


def run_scenario(adapter: ExternalAdapter, scenario: dict[str, Any], k: int) -> dict[str, Any]:
    sid = scenario["scenario_id"]
    adapter.reset(sid)
    adapter.seed(scenario.get("initial_memory_state", []), scenario.get("base_dialogue_prefix", []))
    obs = adapter.write(scenario.get("perturbation_event", ""))
    post = adapter.snapshot()

    ev = read_evidence(scenario)
    prior_value = ev.prior_value if ev else None
    candidate = ev.candidate_value if ev else None
    action_raw, extras = derive_action(prior_value, candidate, post, obs)

    query = scenario.get("evaluation_query", "")
    native = adapter.answer_natively(query) if adapter.answers_natively else None
    if native is not None:
        answer = native
        extras["native_answer"] = True
    else:
        context = adapter.search(query, k=k)
        ctx = "\n".join(f"- {c}" for c in context) or "- (nothing retrieved)"
        answer = chat(ANSWER_SYSTEM, f"Memory snippets:\n{ctx}\n\nQuestion: {query}")
        extras["retrieved_k"] = len(context)

    return {
        "scenario_id": sid,
        "action_raw": action_raw,
        "post_texts": post[:20],
        "answer": answer,
        "extras": extras,
    }


def finalize(out: Path, scenarios_by_id: dict[str, dict[str, Any]]) -> None:
    """Emit metrics_mgp6-compatible prediction files under both mappings."""
    raw_path = out / "raw_results.jsonl"
    rows = [json.loads(l) for l in raw_path.open(encoding="utf-8") if l.strip()]
    for mapping, fname in (
        ("KEEP", "predictions.jsonl"),
        ("ABSTAIN", "predictions_noop_abstain.jsonl"),
    ):
        with (out / fname).open("w", encoding="utf-8") as handle:
            for r in rows:
                scenario = scenarios_by_id.get(r["scenario_id"])
                if scenario is None:
                    continue
                action = r["action_raw"] if r["action_raw"] != "NOOP" else mapping
                handle.write(
                    json.dumps(
                        {
                            "scenario_id": r["scenario_id"],
                            "predicted_action": action,
                            "predicted_memory_state": state_records(scenario, r["post_texts"]),
                            "predicted_answer": r["answer"],
                            "confidence": 0.5,
                            "extras": r.get("extras", {}),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    print(
        f"[{out.name}] wrote predictions.jsonl (NOOP->KEEP) and "
        f"predictions_noop_abstain.jsonl (NOOP->ABSTAIN), n={len(rows)}"
    )


def run_external(adapter_factory, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=HERE.parent / "data" / "mgp6_v2.jsonl")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--limit", type=int, default=0, help="max NEW scenarios this call (0 = all)"
    )
    parser.add_argument("--split", default="", help="train|dev|test|empty=all")
    parser.add_argument("--k", type=int, default=5, help="retrieval depth")
    args = parser.parse_args(argv)

    if not API_KEY:
        raise SystemExit("set OPENROUTER_API_KEY (or OPENAI_API_KEY)")

    adapter: ExternalAdapter = adapter_factory()
    out = args.out or (HERE.parent / "runs" / f"ext_{adapter.name}" / "controller")
    out.mkdir(parents=True, exist_ok=True)
    raw_path = out / "raw_results.jsonl"

    scenarios = load_scenarios(args.gold)
    if args.split:
        scenarios = [s for s in scenarios if s.get("split") == args.split]
    by_id = {s["scenario_id"]: s for s in scenarios}

    have = done_ids(raw_path)
    todo = [s for s in scenarios if s["scenario_id"] not in have]
    if args.limit > 0:
        todo = todo[: args.limit]

    (out / "adapter_meta.json").write_text(
        json.dumps(
            {
                "system": adapter.name,
                "answer_model": ANSWER_MODEL,
                "answers_natively": adapter.answers_natively,
                "mapping": (
                    "SUPERSEDE only when replacement/removal is observable; "
                    "dual-active conflict -> INVALID_COMMIT; "
                    "NOOP->KEEP default; NOOP->ABSTAIN variant file"
                ),
                **adapter.meta(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[{adapter.name}] done={len(have)} todo_now={len(todo)} total={len(scenarios)}")
    errors = 0
    with raw_path.open("a", encoding="utf-8") as handle:
        for i, scenario in enumerate(todo, 1):
            try:
                row = run_scenario(adapter, scenario, args.k)
            except Exception as exc:  # noqa: BLE001 - resume later
                errors += 1
                print(f"[{adapter.name}] ERROR {scenario['scenario_id']}: {exc}", file=sys.stderr)
                continue
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            if i % 10 == 0:
                print(f"[{adapter.name}] {i}/{len(todo)}")
    adapter.close()

    finalize(out, by_id)
    if errors:
        print(
            f"[{adapter.name}] {errors} errors — re-run the same command to "
            f"resume the missing scenarios"
        )
    print(
        f"[{adapter.name}] score with:\n"
        f"  python3 metrics_mgp6.py --gold {args.gold} "
        f"--pred {out / 'predictions.jsonl'} --bootstrap 1000 "
        f"> {out / 'report.json'}"
    )
    return 0
