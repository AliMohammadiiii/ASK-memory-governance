"""Baseline 3 — Recency-pruning memory (M1-W4 §3.3).

The first baseline operating on durable `memory_items` rather than turn-level
retrieval. A `memory_item` is an assertion the assistant has decided to
remember, not a turn that happened to be embedded. This abstraction is the
substrate every later component (extraction, controller, supersession,
audit UI) plugs into.

The four design decisions (see `NOTES/m1w4_design.md` §1a–§1c):

  1. **Trivial extractor.** Every user turn from the resolved memory corpus
     (minus the current session, same anti-leak rule as flat-vector W3 §2.5)
     becomes one `memory_item` with
     `type='episodic_fact'`, `confidence=1.0`. No LLM call. This is a
     deliberate placeholder; the proper extractor lands in M2-W5.

  2. **Capacity N = 50.** When the active count of memory_items would
     exceed N, the oldest active row is evicted (FIFO). Evicted via
     `supersede_evict` — status flip with NO replacement, NO lineage,
     NO `memory_relations` row. The destructiveness of FIFO eviction
     is the central comparison the thesis sets up against the
     controller's lineage-preserving `supersede` chain (proposal §I.7.3).

  3. **Same retrieval as flat-vector.** FAISS `IndexFlatIP` over
     L2-normalized embeddings of `memory_items.text`, top-k=5,
     per-question reset. Pairing recency-pruning with the same retrieval
     as flat-vector isolates **what is stored** (a recency-bounded
     subset of memory_items) rather than **how it is retrieved**.

  4. **Status-flip eviction (no lineage).** See `NOTES/m1w4_design.md`
     §1c. Recency baseline has no version history of evicted items —
     this is the entire point. The controller in M3 will use the
     lineage-preserving `supersede()` primitive instead.

Implementation discipline:
  * Per-question reset of BOTH the SQLite store and the FAISS index.
    Cumulative across-question state is a different baseline (proposal
    §I.5.2).
  * The retrieved-memory block in the rendered prompt MUST contain zero
    items derived from the current session. Test
    `test_no_current_session_leakage_in_retrieved_block` enforces this.
  * The action_log writes:
      - one `Keep` per admission ('trivial extraction admit'),
      - one `Supersede` per FIFO eviction ('FIFO eviction at capacity=50').
  * Empty supporting evidence MUST degenerate cleanly to no-memory.
    Test `test_degenerates_to_no_memory_when_supporting_is_empty`.
  * Same `BaselineAnswer` shape as `NoMemoryBaseline` and
    `FlatVectorBaseline`; the evaluator cannot tell the three apart.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ksa.audit import ActionLogWriter
from ksa.data.longmemeval import LongMemEvalSession, LongMemEvalTurn, memory_session_ids
from ksa.inference.llm import LLM
from ksa.memory import (
    ActionLogEntry,
    ControllerAction,
    MemoryStatus,
    MemoryType,
    connect,
    init_schema,
    insert_active,
    retrieve_active,
    supersede_evict,
)
from ksa.memory import (
    MemoryItem as DBMemoryItem,
)

from .base import BaselineAnswer
from .embeddings import Embedder, TurnEmbedder
from .flat_vector_store import FlatVectorStore
from .flat_vector_store import MemoryItem as RetrievalItem

# Match the flat-vector + no-memory system prompt verbatim. Cross-baseline
# comparisons must not be confounded by system-prompt wording.
DEFAULT_SYSTEM_PROMPT = (
    "Read the provided context and answer the question with only the requested "
    "value, name, date, number, or short phrase. Do not explain. Do not add "
    "surrounding sentence text. If the context is insufficient, answer Unknown."
)

_DEFAULT_K = 5
_DEFAULT_CAPACITY = 50
_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _build_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_PROMPT_DIR)),
        autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )


def _next_action_log_id(path: Path | None) -> int:
    if path is None or not path.exists():
        return 1
    max_id = 0
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                value = row.get("id") if isinstance(row, dict) else None
                if isinstance(value, int):
                    max_id = max(max_id, value)
    except OSError:
        return 1
    return max_id + 1


# --------------------------------------------------------------------- #
# Trivial extractor                                                      #
# --------------------------------------------------------------------- #


@dataclass(frozen=True)
class TrivialExtractedItem:
    """One placeholder MemoryItem produced by the §1a trivial extractor.

    Carries the originating-turn metadata (session_id, turn_idx, role)
    so the rendered retrieved-memory block can show provenance — the
    same fields the flat-vector baseline carries, kept identical for
    apples-to-apples comparison.
    """

    text: str
    role: str
    session_id: str
    turn_idx: int
    timestamp: str | None = None
    type_guess: str = "episodic_fact"
    confidence: float = 1.0


def trivial_extract(
    session: LongMemEvalSession,
    *,
    user_turns_only: bool = True,
) -> list[TrivialExtractedItem]:
    """Trivial extractor: every (user) turn → one placeholder memory_item.

    Args:
        session: a LongMemEvalSession.
        user_turns_only: if True (default), only `role == 'user'` turns
            become items. The rationale: in the proper extractor (M2-W5),
            assistant turns are summarized into the user-facing answer
            stream, not admitted as standalone memories. Mirroring that
            choice here keeps the trivial-vs-proper comparison clean.
    """
    out: list[TrivialExtractedItem] = []
    for i, t in enumerate(session.turns):
        if user_turns_only and t.role != "user":
            continue
        out.append(
            TrivialExtractedItem(
                text=t.content,
                role=t.role,
                session_id=session.session_id,
                turn_idx=i,
                timestamp=t.timestamp,
            )
        )
    return out


def _turn_payload(
    session: LongMemEvalSession,
    turn: LongMemEvalTurn,
    turn_idx: int,
) -> dict[str, Any]:
    return {
        "turn_id": f"{session.session_id}:{turn_idx}",
        "session_id": session.session_id,
        "turn_idx": turn_idx,
        "role": turn.role,
        "content": turn.content,
        "timestamp": turn.timestamp,
    }


def llm_extract(
    extractor: Any,
    session: LongMemEvalSession,
    *,
    max_new_tokens: int = 512,
    seed: int = 0,
    selected_turn_idxs: set[int] | None = None,
    raw_turn_fallback: bool = False,
    progress_label: str | None = None,
) -> list[TrivialExtractedItem]:
    """Run the M2 turn-level extractor and adapt outputs to B3 memory rows."""
    out: list[TrivialExtractedItem] = []
    turns = list(session.turns)
    selected_user_turns = [
        (idx, turn)
        for idx, turn in enumerate(turns)
        if turn.role == "user" and (selected_turn_idxs is None or idx in selected_turn_idxs)
    ]
    total = len(selected_user_turns)
    for ordinal, (idx, turn) in enumerate(selected_user_turns, start=1):
        if progress_label:
            print(
                f"{progress_label}: extract user_turn {ordinal}/{total} {session.session_id}:{idx}",
                flush=True,
            )
        payload = _turn_payload(session, turn, idx)
        prev_payload = _turn_payload(session, turns[idx - 1], idx - 1) if idx > 0 else None
        next_payload = (
            _turn_payload(session, turns[idx + 1], idx + 1) if idx + 1 < len(turns) else None
        )
        extracted = extractor.extract(
            payload,
            (prev_payload, next_payload),
            max_new_tokens=max_new_tokens,
            temperature=0.0,
            seed=seed,
        )
        for item in extracted.items:
            out.append(
                TrivialExtractedItem(
                    text=item.text,
                    role=turn.role,
                    session_id=session.session_id,
                    turn_idx=idx,
                    timestamp=turn.timestamp,
                    type_guess=str(item.type_guess),
                    confidence=float(item.extraction_confidence),
                )
            )
        if raw_turn_fallback:
            raw = TrivialExtractedItem(
                text=turn.content,
                role=turn.role,
                session_id=session.session_id,
                turn_idx=idx,
                timestamp=turn.timestamp,
                type_guess="episodic_fact",
                confidence=0.75,
            )
            if raw.text.casefold() not in {
                item.text.casefold()
                for item in out
                if item.session_id == session.session_id and item.turn_idx == idx
            }:
                out.append(raw)
    return out


# --------------------------------------------------------------------- #
# Corpus lookup                                                          #
# --------------------------------------------------------------------- #


SessionCorpus = Mapping[str, LongMemEvalSession]


def build_session_corpus_for_recency(
    sessions: Iterable[LongMemEvalSession],
) -> dict[str, LongMemEvalSession]:
    """Build a `{session_id: session}` dict over an iterable of sessions.

    Equivalent to `flat_vector.build_session_corpus`; reproduced here as
    a separate symbol so the recency baseline can evolve independently
    if the slice format changes.
    """
    out: dict[str, LongMemEvalSession] = {}
    for s in sessions:
        out[s.session_id] = s
        for support in s.corpus_sessions:
            out[support.session_id] = LongMemEvalSession(
                session_id=support.session_id,
                turns=support.turns,
                question="",
                gold_answer="",
                competency=s.competency,
            )
    return out


# --------------------------------------------------------------------- #
# Baseline                                                               #
# --------------------------------------------------------------------- #


@dataclass
class RecencyPruningBaseline:
    """LLM + SQLite (memory_items) + FAISS retrieval + a single Jinja2 template.

    Args:
        llm: any object satisfying the `ksa.inference.llm.LLM` Protocol.
        embedder: any `Embedder` (default `TurnEmbedder`). The
            FAISS-backed `FlatVectorStore` is built from this embedder
            on each `answer()` call (per-question reset).
        corpus: `{session_id: LongMemEvalSession}` over the slice. Used
            to resolve `supporting_session_ids` into actual turns. May
            be empty; the baseline degenerates to no-memory in that case.
        capacity: FIFO queue size N. Default 50 — see
            `NOTES/m1w4_design.md` §1b. A capacity sweep is **deferred to
            Month-4 ablations**.
        k: top-k for retrieval. Default 5 — same as flat-vector W3.
        prompt_template: name of a `.j2` file in `prompts/`. Defaults
            to `recency_pruning.j2`.
        system_prompt: top of the rendered prompt. Defaults to the
            no-memory wording — same string keeps cross-baseline
            comparisons clean.
        max_new_tokens: 512.
        seed: passed through to the LLM.
    action_log_path: optional path to write the action_log JSONL.
            If provided, the baseline opens an `ActionLogWriter` per
            `answer()` call (mode='a'; the file is truncated by the
            run driver via mode='w' on the first call).
        extractor: optional M2 LLM extractor. When provided, B3 admits
            extractor-emitted memory items instead of the Month-1 trivial
            every-user-turn placeholder.
    """

    llm: LLM
    embedder: Embedder
    corpus: SessionCorpus = field(default_factory=dict)
    extractor: Any | None = None
    capacity: int = _DEFAULT_CAPACITY
    k: int = _DEFAULT_K
    prompt_template: str = "recency_pruning.j2"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_new_tokens: int = 512
    extraction_max_new_tokens: int = 512
    memory_prefilter_top_k: int | None = None
    raw_turn_fallback: bool = False
    progress: bool = False
    seed: int = 0
    action_log_path: Path | None = None
    append_action_log: bool = False

    BASELINE_NAME: str = "recency"

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError(f"capacity must be > 0; got {self.capacity}")
        if self.k <= 0:
            raise ValueError(f"k must be > 0; got {self.k}")
        self._env = _build_jinja_env()
        self._template = self._env.get_template(self.prompt_template)
        # The action_log writer for the FIRST answer() call uses mode='w'
        # (truncate); subsequent calls use mode='a' (append). The
        # `_action_log_started` flag tracks this.
        self._action_log_started = self.append_action_log
        # Monotonic ID for action_log entries.
        self._next_log_id = (
            _next_action_log_id(self.action_log_path) if self.append_action_log else 1
        )

    # --- factory helper --------------------------------------------- #

    @classmethod
    def with_default_embedder(
        cls,
        llm: LLM,
        corpus: SessionCorpus | None = None,
        *,
        capacity: int = _DEFAULT_CAPACITY,
        k: int = _DEFAULT_K,
        device: str = "cpu",
        action_log_path: Path | None = None,
    ) -> RecencyPruningBaseline:
        embedder = TurnEmbedder(device=device)
        return cls(
            llm=llm,
            embedder=embedder,
            corpus=corpus or {},
            capacity=capacity,
            k=k,
            action_log_path=action_log_path,
        )

    # --- extraction -------------------------------------------------- #

    def _items_for_session(self, session: LongMemEvalSession) -> list[TrivialExtractedItem]:
        """All extracted items the question can index.

        Mirrors the flat-vector W3 §2.5 anti-leak rule. Cleaned LongMemEval
        rows use attached haystack sessions; legacy JSONL fixtures use
        `supporting_session_ids`.
        """
        out: list[TrivialExtractedItem] = []
        memory_ids = memory_session_ids(session)
        resolved = [(sid, self.corpus.get(sid)) for sid in memory_ids]
        unresolved = [sid for sid, other in resolved if other is None]
        supporting_sessions = [other for _sid, other in resolved if other is not None]
        if self.progress:
            print(
                f"[recency] {session.session_id}: start; "
                f"memory_sessions={len(memory_ids)} resolved={len(supporting_sessions)} "
                f"unresolved={len(unresolved)}",
                flush=True,
            )

        selected_by_session = self._prefilter_memory_turns(session, supporting_sessions)
        if selected_by_session is not None and self.progress:
            total_user_turns = sum(
                1 for other in supporting_sessions for turn in other.turns if turn.role == "user"
            )
            selected_count = sum(len(turns) for turns in selected_by_session.values())
            print(
                f"[recency] {session.session_id}: memory_prefilter "
                f"selected={selected_count}/{total_user_turns} user_turns",
                flush=True,
            )

        ingested_idx = 0
        for sid, other in resolved:
            if other is None:
                continue
            selected_turns = (
                selected_by_session.get(sid, set()) if selected_by_session is not None else None
            )
            if selected_by_session is not None and not selected_turns:
                continue
            ingested_idx += 1
            if self.progress:
                print(
                    f"[recency] {session.session_id}: ingest memory_session "
                    f"{ingested_idx}/{len(supporting_sessions)} {sid} turns={len(other.turns)}",
                    flush=True,
                )
            if self.extractor is None:
                out.extend(trivial_extract(other, user_turns_only=True))
            else:
                out.extend(
                    llm_extract(
                        self.extractor,
                        other,
                        max_new_tokens=self.extraction_max_new_tokens,
                        seed=self.seed,
                        selected_turn_idxs=selected_turns,
                        raw_turn_fallback=self.raw_turn_fallback,
                        progress_label=(
                            f"[recency] {session.session_id}: memory {ingested_idx}"
                            if self.progress
                            else None
                        ),
                    )
                )
        if self.progress:
            print(
                f"[recency] {session.session_id}: extracted_items={len(out)}",
                flush=True,
            )
        return out

    def _prefilter_memory_turns(
        self,
        session: LongMemEvalSession,
        supporting_sessions: list[LongMemEvalSession],
    ) -> dict[str, set[int]] | None:
        """Select top-k haystack user turns before expensive LLM extraction."""
        if self.extractor is None:
            return None
        if self.memory_prefilter_top_k is None:
            return None
        if self.memory_prefilter_top_k <= 0:
            return {}
        candidates: list[RetrievalItem] = []
        for other in supporting_sessions:
            for idx, turn in enumerate(other.turns):
                if turn.role != "user":
                    continue
                candidates.append(
                    RetrievalItem(
                        text=turn.content,
                        role=turn.role,
                        session_id=other.session_id,
                        turn_idx=idx,
                        timestamp=turn.timestamp,
                    )
                )
        if not candidates:
            return {}
        store = FlatVectorStore(embedder=self.embedder)
        store.add(candidates)
        selected = store.search(session.question, k=self.memory_prefilter_top_k)
        out: dict[str, set[int]] = {}
        for hit in selected:
            out.setdefault(hit.item.session_id, set()).add(hit.item.turn_idx)
        return out

    # --- per-question lifecycle ------------------------------------- #

    def _admit_with_fifo_eviction(
        self,
        conn: Any,
        items: list[TrivialExtractedItem],
        session_id: str,
        log_writer: ActionLogWriter | None,
    ) -> list[tuple[int, TrivialExtractedItem]]:
        """Admit each item; evict FIFO when at capacity. Returns (db_id, item) pairs.

        The 'evict-then-admit' order matters: it guarantees the active
        count never exceeds `self.capacity`. Evicting an item is a
        status-flip on the oldest active row in the SQLite store, with
        no lineage — see `NOTES/m1w4_design.md` §1c.

        For each admission AND each eviction, an action_log entry is
        written if a writer is provided.
        """
        admitted: list[tuple[int, TrivialExtractedItem]] = []
        for item in items:
            # Check capacity. The store is fresh per question, so the
            # active count grows monotonically inside this loop until
            # eviction kicks in.
            actives = retrieve_active(conn)
            if len(actives) >= self.capacity:
                # Oldest-active = lowest id. retrieve_active already
                # orders by id ASC; take the first.
                evictee = actives[0]
                assert evictee.id is not None
                supersede_evict(conn, prior_id=evictee.id)
                if log_writer is not None:
                    log_writer.write(
                        ActionLogEntry(
                            id=self._next_log_id,
                            timestamp=datetime.now(UTC),
                            action=ControllerAction.SUPERSEDE,
                            candidate_text="(no replacement — FIFO eviction)",
                            rationale=f"FIFO eviction at capacity={self.capacity}",
                            session_id=session_id,
                            baseline=self.BASELINE_NAME,
                            prior_memory_id=evictee.id,
                            resulting_memory_id=None,
                        )
                    )
                    self._next_log_id += 1

            # Admit.
            db_item = DBMemoryItem(
                id=None,
                type=MemoryType(item.type_guess),
                text=item.text,
                confidence=item.confidence,
                status=MemoryStatus.ACTIVE,
            )
            new_id = insert_active(conn, db_item)
            admitted.append((new_id, item))
            if log_writer is not None:
                log_writer.write(
                    ActionLogEntry(
                        id=self._next_log_id,
                        timestamp=datetime.now(UTC),
                        action=ControllerAction.KEEP,
                        candidate_text=item.text,
                        rationale=(
                            "M2 LLM extraction admit"
                            if self.extractor is not None
                            else "trivial extraction admit"
                        ),
                        session_id=session_id,
                        baseline=self.BASELINE_NAME,
                        candidate_type=MemoryType(item.type_guess),
                        prior_memory_id=None,
                        resulting_memory_id=new_id,
                    )
                )
                self._next_log_id += 1
        return admitted

    # --- prompt rendering ------------------------------------------- #

    def render_prompt(
        self,
        session: LongMemEvalSession,
        retrieved: list[Any],  # list[RetrievedItem] from FlatVectorStore
    ) -> str:
        turn_dicts = [{"role": t.role, "content": t.content} for t in session.turns]
        retrieved_dicts = [
            {
                "score": r.score,
                "role": r.item.role,
                "session_id": r.item.session_id,
                "turn_idx": r.item.turn_idx,
                "text": r.item.text,
            }
            for r in retrieved
        ]
        return self._template.render(
            system_prompt=self.system_prompt,
            retrieved_memory=retrieved_dicts,
            turns=turn_dicts,
            question=session.question,
        )

    # --- generation -------------------------------------------------- #

    def answer(self, session: LongMemEvalSession) -> BaselineAnswer:
        """Generate one answer for one session.

        Steps (per task §3.3):
          1. Reset the SQLite memory store (per-question reset).
          2. Trivial extraction: every user turn from the resolvable
             supporting sessions (minus the current) → one memory_item.
          3. FIFO admission with eviction at `self.capacity`.
          4. Build a fresh FAISS index over the active memory_items.
          5. Retrieve top-k by cosine similarity to the question.
          6. Render the prompt; generate; return BaselineAnswer.
        """
        # 1. Reset. Per-question SQLite is in-memory; we open a fresh
        # connection each call so cross-question state never leaks.
        conn = connect(":memory:")
        try:
            init_schema(conn)

            # Open the action_log writer if requested. First answer()
            # truncates; subsequent calls append.
            log_cm: ActionLogWriter | None = None
            if self.action_log_path is not None:
                mode = "w" if not self._action_log_started else "a"
                log_cm = ActionLogWriter(
                    self.action_log_path,
                    baseline=self.BASELINE_NAME,
                    mode=mode,
                )
                log_cm.__enter__()
                self._action_log_started = True

            try:
                # 2. Extract.
                items = self._items_for_session(session)
                memory_ids = memory_session_ids(session)
                unresolved = [sid for sid in memory_ids if sid not in self.corpus]

                # 3. Admit with FIFO eviction.
                admitted = self._admit_with_fifo_eviction(
                    conn=conn,
                    items=items,
                    session_id=session.session_id,
                    log_writer=log_cm,
                )
                if self.progress:
                    print(
                        f"[recency] {session.session_id}: admitted={len(admitted)} "
                        f"capacity={self.capacity}",
                        flush=True,
                    )

                # 4. Build retrieval index from the CURRENTLY ACTIVE
                # memory_items only — evicted (superseded) items must
                # NOT appear. This is the active-only filter that the
                # whole substrate exists to provide.
                store = FlatVectorStore(embedder=self.embedder)
                actives_now = retrieve_active(conn)
                # We need the trivial-extracted item metadata to render
                # provenance — recover it by id from `admitted`.
                admitted_by_id = {db_id: itm for db_id, itm in admitted}
                retrieval_items: list[RetrievalItem] = []
                for active in actives_now:
                    if active.id is None:
                        continue
                    src = admitted_by_id.get(active.id)
                    if src is None:
                        continue  # defensive — shouldn't happen
                    retrieval_items.append(
                        RetrievalItem(
                            text=active.text,
                            role=src.role,
                            session_id=src.session_id,
                            turn_idx=src.turn_idx,
                            timestamp=src.timestamp,
                        )
                    )
                store.add(retrieval_items)

                # 5. Retrieve.
                retrieved = store.search(session.question, k=self.k)
                if self.progress:
                    print(
                        f"[recency] {session.session_id}: retrieved={len(retrieved)}",
                        flush=True,
                    )

                # 6. Render + generate.
                prompt = self.render_prompt(session, retrieved)
                resp = self.llm.generate(
                    prompt,
                    max_new_tokens=self.max_new_tokens,
                    temperature=0.0,
                    seed=self.seed,
                )
                text = resp.text.strip()

                n_active = len(actives_now)
                n_evicted = len(admitted) - n_active
                if self.progress:
                    print(
                        f"[recency] {session.session_id}: done; active={n_active} "
                        f"evicted={n_evicted}",
                        flush=True,
                    )
                return BaselineAnswer(
                    session_id=session.session_id,
                    text=text,
                    prompt_tokens=resp.prompt_tokens,
                    completion_tokens=resp.completion_tokens,
                    latency_ms=resp.latency_ms,
                    raw_prompt=prompt,
                    seed=self.seed,
                    model_id=resp.model_id,
                    baseline=self.BASELINE_NAME,
                    extras={
                        "k": self.k,
                        "capacity": self.capacity,
                        "n_admitted": len(admitted),
                        "n_active": n_active,
                        "n_evicted": n_evicted,
                        "n_retrieved": len(retrieved),
                        "extractor_mode": "m2_llm" if self.extractor is not None else "trivial",
                        "memory_prefilter_top_k": self.memory_prefilter_top_k,
                        "raw_turn_fallback": self.raw_turn_fallback,
                        "smrr_status": "not_computed_longmemeval_lacks_gold_supersession",
                        "stale_retrieval_count": 0,
                        "smrr_denominator": 0,
                        "retrieval_scores": [r.score for r in retrieved],
                        "retrieval_session_ids": [r.item.session_id for r in retrieved],
                        "retrieval_turn_idxs": [r.item.turn_idx for r in retrieved],
                        "retrieval_memory_ids": [
                            db_id for active in actives_now for db_id in [active.id]
                        ][: self.k],
                        "embedder_model_id": getattr(self.embedder, "model_id", "unknown-embedder"),
                        "memory_session_ids": list(memory_ids),
                        "unresolved_memory_ids": unresolved,
                        "supporting_session_ids": list(session.supporting_session_ids),
                        "unresolved_supporting_ids": unresolved,
                        "llm_call": dict(resp.metadata),
                    },
                )
            finally:
                if log_cm is not None:
                    log_cm.__exit__(None, None, None)
        finally:
            conn.close()
