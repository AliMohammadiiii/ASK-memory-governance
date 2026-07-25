"""End-to-end smoke: one LongMemEval session → LLM → SQLite + action_log.

Purpose (M1-W1 §3.3): catch integration bugs now, not in Month 4. The script
deliberately uses the thinnest possible pipeline — no controller logic, no
retrieval — to prove only that the plumbing works.

Usage:
    # Real model on the GPU runner:
    python scripts/smoke_e2e.py \
        --slice data/slices/longmemeval_s_50_seed0.jsonl \
        --session-id lme-s-00012 \
        --db /tmp/smoke.sqlite

    # CPU / dev-machine path with the deterministic fake LLM:
    python scripts/smoke_e2e.py \
        --slice data/slices/longmemeval_s_50_seed0.jsonl \
        --session-id lme-s-00012 \
        --db /tmp/smoke.sqlite \
        --fake
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ask.audit import ActionLogWriter  # noqa: E402
from ask.data.longmemeval import iter_longmemeval_s  # noqa: E402
from ask.inference.llm import LLM  # noqa: E402
from ask.memory import (  # noqa: E402
    ActionLogEntry,
    ControllerAction,
    MemoryItem,
    MemoryType,
    connect,
    init_schema,
    insert_active,
)


def _build_prompt(session_turns: list[dict[str, str]], question: str) -> str:
    convo = "\n".join(f"{t['role'].upper()}: {t['content']}" for t in session_turns)
    return (
        "Read the dialog below and answer the question with a single short "
        "sentence. Do not explain. Do not repeat the question.\n\n"
        "----- DIALOG -----\n"
        f"{convo}\n"
        "----- QUESTION -----\n"
        f"{question}\n"
        "----- ANSWER (one short sentence) -----\n"
    )


def run_smoke(
    slice_path: Path,
    session_id: str,
    db_path: Path,
    log_path: Path,
    llm: LLM,
) -> dict:
    """Run the smoke pipeline and return a dict summarizing what happened."""
    # 1) Find the session.
    session = None
    for s in iter_longmemeval_s(slice_path):
        if s.session_id == session_id:
            session = s
            break
    if session is None:
        raise SystemExit(f"session_id {session_id!r} not found in {slice_path}")

    # 2) Generate.
    prompt = _build_prompt([t.to_dict() for t in session.turns], session.question)
    resp = llm.generate(prompt, max_new_tokens=128, temperature=0.0, seed=0)

    # 3) Open SQLite, init schema, write a dummy memory item (for plumbing only).
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = connect(db_path)
    init_schema(conn)

    candidate_text = (
        f"[smoke] question={session.question!r} "
        f"answer={resp.text[:200]!r}"
    )
    mem_id = insert_active(
        conn,
        MemoryItem(
            id=None,
            type=MemoryType.EPISODIC_FACT,
            text=candidate_text,
            confidence=0.5,  # placeholder — real value comes from the extractor in M2
        ),
    )

    # 4) Write a single action_log entry. No real controller decision yet —
    #    this is just plumbing — so we record action='Keep' with a synthetic
    #    feature snapshot. The validator must accept it.
    log_id = 1
    entry = ActionLogEntry(
        id=log_id,
        timestamp=datetime.now(UTC),
        action=ControllerAction.KEEP,
        candidate_text=candidate_text,
        rationale="[smoke] plumbing test — no controller logic invoked",
        prior_memory_id=None,
        resulting_memory_id=mem_id,
        feature_c=None, feature_e=None, feature_f=None, feature_r=None, feature_rho=None,
        s_rev=None, s_abs=None, theta_sup=None, theta_abs=None,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists():
        log_path.unlink()
    with ActionLogWriter(log_path) as w:
        w.write(entry)

    # 5) Read everything back.
    rows = conn.execute(
        "SELECT id, type, text, status FROM memory_items"
    ).fetchall()
    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    conn.close()

    return {
        "session_id": session.session_id,
        "model_id": resp.model_id,
        "prompt_tokens": resp.prompt_tokens,
        "completion_tokens": resp.completion_tokens,
        "latency_ms": round(resp.latency_ms, 1),
        "memory_rows": [dict(r) for r in rows],
        "action_log_lines": len(log_lines),
        "db_path": str(db_path),
        "log_path": str(log_path),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--slice", required=True, type=Path)
    p.add_argument("--session-id", required=True)
    p.add_argument("--db", required=True, type=Path)
    p.add_argument("--log", type=Path, default=None,
                   help="Path to action_log JSONL (default: alongside the DB)")
    p.add_argument("--fake", action="store_true",
                   help="Use the deterministic FakeLLM. Hermetic, no GPU/network.")
    p.add_argument("--ollama", action="store_true",
                   help="Use a local Ollama daemon. Pair with --ollama-model.")
    p.add_argument("--ollama-model", default="gemma3:4b",
                   help="Ollama model tag, e.g. gemma3:4b or qwen2.5:7b-instruct.")
    p.add_argument("--ollama-host", default="http://localhost:11434",
                   help="Ollama daemon URL (default: http://localhost:11434).")
    args = p.parse_args()

    if args.fake:
        from ask.inference.fake import FakeLLM
        llm: LLM = FakeLLM()
    elif args.ollama:
        from ask.inference.ollama import OllamaLLM
        llm = OllamaLLM(model_id=args.ollama_model, host=args.ollama_host)
    else:
        from ask.inference.llm import build_llm
        llm = build_llm()

    log_path = args.log or args.db.with_suffix(".action_log.jsonl")

    summary = run_smoke(
        slice_path=args.slice,
        session_id=args.session_id,
        db_path=args.db,
        log_path=log_path,
        llm=llm,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
