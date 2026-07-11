"""Baseline 2 — Flat-vector memory (M1-W3 §3.3).

The field's de-facto strawman: a FAISS-backed top-k retrieval system over
turn-level embeddings, concatenated into the prompt at response time. No
versioning, no typing, no supersession, no recency weighting — just
"retrieve the k nearest turns by cosine similarity and put them in the
prompt".

The thesis claim that revision governance matters only holds if a
**competently implemented** flat-vector system fails on the competencies
the controller targets. So this baseline is implemented to median-of-
literature defaults (see `NOTES/m1w3_design.md` §2):

  * `sentence-transformers/all-MiniLM-L6-v2`, no fine-tuning
  * one turn = one indexed item, role-tagged ("[USER] ..." / "[ASSISTANT] ...")
  * `IndexFlatIP` over L2-normalized embeddings (cosine)
  * top-k = 5
  * per-question reset; index the question's allowed memory corpus, excluding
    the current session_id. On cleaned LongMemEval records this is
    `haystack_sessions`, not oracle `answer_session_ids`.

Implementation discipline:
  * The retrieved-memory block in the rendered prompt MUST contain zero
    turns from the current session. Test
    `test_no_current_session_leakage_in_retrieved_block` enforces this.
  * Empty supporting evidence MUST degenerate cleanly to no-memory (an
    empty retrieved-memory block, plus the dialog and question). Test
    `test_degenerates_to_no_memory_when_supporting_is_empty` enforces.
  * Same `BaselineAnswer` shape as `NoMemoryBaseline`; the evaluator
    cannot tell the two apart. That's the point of the shared shape.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ksa.data.longmemeval import LongMemEvalSession, memory_session_ids
from ksa.inference.llm import LLM

from .base import BaselineAnswer
from .embeddings import TurnEmbedder
from .flat_vector_store import FlatVectorStore, MemoryItem, RetrievedItem

# Match `NoMemoryBaseline.DEFAULT_SYSTEM_PROMPT` so cross-baseline numbers
# don't drift on system-prompt wording. The retrieved-memory framing is
# in the prompt template, not in the system prompt — the system prompt
# stays minimal.
DEFAULT_SYSTEM_PROMPT = (
    "Read the provided context and answer the question with only the requested "
    "value, name, date, number, or short phrase. Do not explain. Do not add "
    "surrounding sentence text. If the context is insufficient, answer Unknown."
)

_DEFAULT_K = 5
_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _build_jinja_env() -> Environment:
    """Module-level Jinja env mirroring the no-memory baseline's setup."""
    return Environment(
        loader=FileSystemLoader(str(_PROMPT_DIR)),
        autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )


# --------------------------------------------------------------------- #
# Corpus lookup                                                          #
# --------------------------------------------------------------------- #


SessionCorpus = Mapping[str, LongMemEvalSession]
"""A `dict[session_id, LongMemEvalSession]` over the slice / corpus.

Used to resolve per-question memory session IDs into actual turns. The baseline
does not load this itself — `scripts/run_baseline.py` builds it from the
slice JSONL once and passes it in. This keeps the baseline pure and
testable.
"""


def build_session_corpus(sessions: Iterable[LongMemEvalSession]) -> dict[str, LongMemEvalSession]:
    """Build a `{session_id: session}` dict over an iterable of sessions.

    On duplicate IDs, last-write wins — but the LongMemEval-S slicer
    guarantees uniqueness, so this is just defensive.
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


def _session_to_memory_items(session: LongMemEvalSession) -> list[MemoryItem]:
    """Convert one session's turns into a list of indexable `MemoryItem`s."""
    items: list[MemoryItem] = []
    for i, t in enumerate(session.turns):
        items.append(
            MemoryItem(
                text=t.content,
                role=t.role,
                session_id=session.session_id,
                turn_idx=i,
                timestamp=t.timestamp,
            )
        )
    return items


# --------------------------------------------------------------------- #
# Baseline                                                               #
# --------------------------------------------------------------------- #


@dataclass
class FlatVectorBaseline:
    """LLM + FAISS retrieval + a single Jinja2 template.

    Args:
        llm: any object satisfying the `ksa.inference.llm.LLM` Protocol.
            Used to generate the answer; uncoupled from the embedder.
        store: a `FlatVectorStore`. The baseline `clear()`s and re-adds
            into this store on every `answer()` call (per-question reset).
            The caller may pass a fresh store every call too — both work.
        corpus: `{session_id: LongMemEvalSession}` over the slice. Used
            to resolve `supporting_session_ids` into turns. May be empty;
            the baseline degenerates to no-memory in that case.
        k: top-k for retrieval. Default 5 (see `NOTES/m1w3_design.md` §2.4).
            A k-sweep is **deferred to M4 ablations** — do not sweep here.
        prompt_template: name of a `.j2` file in `prompts/`. Defaults to
            `flat_vector.j2`.
        system_prompt: top of the rendered prompt. Defaults to the
            no-memory wording — same string keeps cross-baseline
            comparisons clean.
        max_new_tokens: 512 — same as `NoMemoryBaseline`.
        seed: passed through to the LLM.
    """

    llm: LLM
    store: FlatVectorStore
    corpus: SessionCorpus = field(default_factory=dict)
    k: int = _DEFAULT_K
    prompt_template: str = "flat_vector.j2"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_new_tokens: int = 512
    seed: int = 0

    BASELINE_NAME: str = "flat_vector"

    def __post_init__(self) -> None:
        self._env = _build_jinja_env()
        self._template = self._env.get_template(self.prompt_template)

    # --- factory helper --------------------------------------------- #

    @classmethod
    def with_default_embedder(
        cls,
        llm: LLM,
        corpus: SessionCorpus | None = None,
        *,
        k: int = _DEFAULT_K,
        device: str = "cpu",
    ) -> FlatVectorBaseline:
        """Build a `FlatVectorBaseline` with the M1-W3 default embedder + store.

        Used by `scripts/run_baseline.py`. The dev path that doesn't
        want the real MiniLM weights can construct a `FlatVectorStore`
        directly with a `FakeEmbedder` and pass it in.
        """
        embedder = TurnEmbedder(device=device)
        store = FlatVectorStore(embedder=embedder)
        return cls(llm=llm, store=store, corpus=corpus or {}, k=k)

    # --- index building --------------------------------------------- #

    def _items_for_session(self, session: LongMemEvalSession) -> list[MemoryItem]:
        """Turns to index for `session`'s question.

        On cleaned LongMemEval rows, index every turn from the attached
        haystack corpus. Legacy JSONL rows that lack attached corpus sessions
        keep the original `supporting_session_ids` behavior. Lookup is via
        `self.corpus`; missing IDs are silently dropped and surfaced in
        `extras`.
        """
        items: list[MemoryItem] = []
        for sid in memory_session_ids(session):
            other = self.corpus.get(sid)
            if other is None:
                continue
            items.extend(_session_to_memory_items(other))
        return items

    # --- prompt rendering ------------------------------------------- #

    def render_prompt(
        self,
        session: LongMemEvalSession,
        retrieved: list[RetrievedItem],
    ) -> str:
        """Render the LLM-facing prompt with the retrieved-memory block.

        Returns the exact text we will hand to `llm.generate`.
        """
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
        """Generate one answer for one session. Synchronous.

        Steps (per task §3.3):
          1. Reset the store.
          2. Index every turn from the allowed memory corpus minus current.
          3. Build retrieval query from question text alone (no expansion).
          4. Retrieve top-k turns.
          5. Render the prompt with the retrieved-memory block.
          6. Generate; return BaselineAnswer with retrieval telemetry in
             `extras`.
        """
        # 1. Reset.
        self.store.clear()

        # 2. Index the allowed memory corpus (minus current).
        items = self._items_for_session(session)
        memory_ids = memory_session_ids(session)
        unresolved = [sid for sid in memory_ids if sid not in self.corpus]
        self.store.add(items)

        # 3-4. Retrieve top-k (empty if store is empty — degenerate path).
        retrieved = self.store.search(session.question, k=self.k)

        # 5. Render.
        prompt = self.render_prompt(session, retrieved)

        # 6. Generate.
        resp = self.llm.generate(
            prompt,
            max_new_tokens=self.max_new_tokens,
            temperature=0.0,
            seed=self.seed,
        )
        text = resp.text.strip()

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
                "n_indexed": self.store.size,
                "n_retrieved": len(retrieved),
                "retrieval_scores": [r.score for r in retrieved],
                "retrieval_session_ids": [r.item.session_id for r in retrieved],
                "retrieval_turn_idxs": [r.item.turn_idx for r in retrieved],
                "embedder_model_id": getattr(
                    self.store.embedder, "model_id", "unknown-embedder"
                ),
                "memory_session_ids": list(memory_ids),
                "unresolved_memory_ids": unresolved,
                "supporting_session_ids": list(session.supporting_session_ids),
                "unresolved_supporting_ids": unresolved,
                "llm_call": dict(resp.metadata),
            },
        )
