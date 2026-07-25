"""FAISS-backed flat vector store for the M1-W3 flat-vector baseline (§3.2).

Wraps a FAISS `IndexFlatIP` (exact inner-product over L2-normalized rows
= cosine similarity) plus a parallel list of `MemoryItem` records keyed
by FAISS row index. The API is deliberately narrow:

  * `add(items)` — embed and append.
  * `search(query, k)` — return top-k items + scores.
  * `clear()` — reset the index between questions.

The narrowness is intentional. Week 4's recency-pruning baseline and
Month 3's controller both need a memory store, but with **different
semantics** (FIFO eviction; status / supersession). A fat shared
interface here would leak those semantics back into the flat baseline
and contaminate cross-baseline comparisons. Carry over the lesson from
M1-W2 §3.0: every later baseline that needs more API gets its own
class, not a feature flag on this one.

Index choice: `IndexFlatIP` (exact). At the M1-W3 scale (50 sessions ×
≤ 30 turns/session × 384 dims ≈ 1500 vectors × 384 floats ≈ 2.3 MB),
exact search is trivially fast — < 1 ms/query on CPU. IVF/HNSW are only
meaningful at orders of magnitude larger scale (proposal §I.7.1
explicitly defers them).

The session-reset policy (per-question vs. cumulative) is documented in
`NOTES/m1w3_design.md` §2.5: the `FlatVectorBaseline` calls `clear()`
before each question and indexes only that question's
`supporting_session_ids` minus the current session. The store itself
is policy-free — `clear()` exists, the *baseline* decides when to use it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .embeddings import Embedder, role_tag


class _NumpyFlatIPIndex:
    """Exact inner-product index, used only when ``faiss-cpu`` is unavailable.

    ``faiss.IndexFlatIP`` is itself a brute-force exact inner-product scan, so
    this reproduces its results bit-for-bit (same float32 vectors, same metric,
    same descending sort). It exists purely so the controller/baselines run in
    minimal environments (e.g. a fresh Colab kernel without faiss) instead of
    crashing in retrieval. When faiss IS installed, it is never constructed and
    behavior is identical to before.
    """

    def __init__(self, dim: int) -> None:
        self._dim = int(dim)
        self._vecs: np.ndarray = np.empty((0, self._dim), dtype=np.float32)

    @property
    def ntotal(self) -> int:
        return int(self._vecs.shape[0])

    def add(self, vecs: np.ndarray) -> None:
        self._vecs = np.vstack([self._vecs, np.asarray(vecs, dtype=np.float32)])

    def search(self, q: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        q = np.asarray(q, dtype=np.float32)
        if self.ntotal == 0:
            return (
                np.zeros((q.shape[0], 0), dtype=np.float32),
                np.full((q.shape[0], 0), -1, dtype=np.int64),
            )
        eff_k = min(int(k), self.ntotal)
        scores = q @ self._vecs.T  # (nq, ntotal) inner products
        # top-eff_k per row, sorted descending — matches IndexFlatIP ordering.
        idx_part = np.argpartition(-scores, eff_k - 1, axis=1)[:, :eff_k]
        rows = np.arange(scores.shape[0])[:, None]
        order = np.argsort(-scores[rows, idx_part], axis=1)
        idxs = idx_part[rows, order]
        return scores[rows, idxs].astype(np.float32), idxs.astype(np.int64)


# --------------------------------------------------------------------- #
# Item dataclasses                                                       #
# --------------------------------------------------------------------- #


@dataclass(frozen=True)
class MemoryItem:
    """One thing the store can index and return.

    Carries enough metadata for:
      * embedding the text (`text`, `role`);
      * audit / debugging in `judgments.jsonl` (`session_id`, `turn_idx`,
        `timestamp`).

    Frozen so `add()` callers cannot mutate items and silently desync the
    parallel metadata list from the FAISS rows.
    """

    text: str
    role: str  # "user" | "assistant" (others tolerated by `role_tag`)
    session_id: str
    turn_idx: int
    timestamp: str | None = None

    def embed_text(self) -> str:
        """Return the role-tagged form that the embedder sees.

        Using `embeddings.role_tag` here (and only here) keeps a single
        source of truth for the on-the-wire embedded representation.
        Tests assert that the prompt template renders this same string.
        """
        return role_tag(self.role, self.text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "role": self.role,
            "session_id": self.session_id,
            "turn_idx": self.turn_idx,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class RetrievedItem:
    """One memory item returned from `FlatVectorStore.search()`.

    `score` is the inner-product between L2-normalized vectors, i.e.
    cosine similarity in [-1, 1]. With `IndexFlatIP` and unit-norm rows
    this is what the literature reports.
    """

    item: MemoryItem
    score: float
    rank: int  # 0-indexed position in the descending top-k list

    def to_dict(self) -> dict[str, Any]:
        return {
            "item": self.item.to_dict(),
            "score": float(self.score),
            "rank": int(self.rank),
        }


# --------------------------------------------------------------------- #
# Store                                                                  #
# --------------------------------------------------------------------- #


@dataclass
class FlatVectorStore:
    """FAISS `IndexFlatIP` over L2-normalized embeddings + parallel metadata.

    Args:
        embedder: any object satisfying the `Embedder` Protocol. Provides
            `embedding_dim` and `embed(texts) -> (n, dim) float32`.
        index_factory: a FAISS `index_factory` string. Default `"Flat"`
            instantiates an `IndexFlatIP`. Anything more elaborate
            (`"IVF*"`, `"HNSW*"`, etc.) is explicitly out of M1-W3 scope
            (task §7).

    Persistence: in-memory only. Re-running a baseline rebuilds the
    index from the slice. M1-W3 has no on-disk index format — adding one
    would obscure the per-question reset semantics that are the central
    documented choice.
    """

    embedder: Embedder
    index_factory: str = "Flat"

    _index: Any = field(default=None, init=False, repr=False)
    _items: list[MemoryItem] = field(default_factory=list, init=False, repr=False)
    # The dimension we built the FAISS index against. Tracked separately
    # from `self.embedder.embedding_dim` so that swapping the embedder
    # mid-life (a configuration error in the wild, but possible) raises
    # in `add()` instead of silently producing FAISS dim assertions
    # deep in C++ — see `test_dim_mismatch_raises_on_add`.
    _index_dim: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        # Build the empty index up front so `dim` mismatches surface at
        # construction time, not on the first add(). MiniLM-L6-v2 is
        # 384-dim and known by `TurnEmbedder` without paying a load.
        self._index_dim = int(self.embedder.embedding_dim)
        self._index = self._new_index()

    # --- internal ---------------------------------------------------- #

    def _new_index(self) -> Any:
        """Construct a fresh FAISS index with the configured factory.

        Imported lazily so test envs without `faiss-cpu` can still import
        this module — though every test in `test_flat_vector_store.py`
        does require faiss.
        """
        try:
            import faiss  # type: ignore[import-not-found]
        except ImportError:
            # No faiss in this environment (e.g. a fresh Colab kernel). Fall
            # back to an exact numpy inner-product index, which is equivalent
            # to IndexFlatIP at this scale. Only the default "Flat" factory can
            # be emulated; anything else genuinely needs faiss.
            dim = int(self._index_dim) if self._index_dim else int(self.embedder.embedding_dim)
            if self.index_factory != "Flat":
                raise RuntimeError(
                    f"index_factory={self.index_factory!r} requires faiss-cpu; "
                    "install with: pip install 'faiss-cpu>=1.8,<2'"
                )
            return _NumpyFlatIPIndex(dim)
        # Use the dim we've recorded for this store (set in __post_init__
        # and re-affirmed on each `clear()`). Reading from the embedder
        # here would let a swapped embedder build a fresh index at the
        # wrong dim and silently mask the mismatch.
        dim = int(self._index_dim) if self._index_dim else int(self.embedder.embedding_dim)
        if self.index_factory == "Flat":
            # IndexFlatIP — exact inner product. With L2-normalized rows
            # this is cosine similarity, which is what the literature
            # uses (see `NOTES/m1w3_design.md` §2.1).
            return faiss.IndexFlatIP(dim)
        # `index_factory` lets a future ablation try IVF without
        # rewriting this class — but the metric must remain inner
        # product to preserve the cosine semantics.
        return faiss.index_factory(dim, self.index_factory, faiss.METRIC_INNER_PRODUCT)

    # --- public API -------------------------------------------------- #

    @property
    def size(self) -> int:
        """Number of indexed items. `assert store.size == store._index.ntotal`."""
        # The two should never disagree by construction; surface them
        # consistently for callers.
        return len(self._items)

    @property
    def embedding_dim(self) -> int:
        """The dim the FAISS index was built against.

        Note: NOT read from `self.embedder` — see the comment on
        `_index_dim` for why.
        """
        return int(self._index_dim)

    def add(self, items: list[MemoryItem]) -> None:
        """Embed each item's `embed_text()` and append to the index.

        Atomic with respect to crashes mid-batch: the FAISS `add` and the
        metadata `extend` are sequential, but neither is interrupted by
        Python signal handling under normal circumstances. If a crash
        leaves them desynced, `size` (which reads from `self._items`)
        will disagree with `_index.ntotal` and downstream `search` will
        notice. The Week-3 baselines do not run with a recovery path —
        a crashed run is restarted, not resumed.
        """
        if not items:
            return
        texts = [it.embed_text() for it in items]
        vecs = self.embedder.embed(texts)
        if vecs.dtype != np.float32:
            # `Embedder` Protocol promises float32 but be defensive — a
            # wrong dtype here would silently produce garbage in FAISS.
            vecs = vecs.astype(np.float32, copy=False)
        if vecs.shape[1] != self.embedding_dim:
            raise ValueError(
                f"embedder returned dim={vecs.shape[1]} but store was built "
                f"for dim={self.embedding_dim} — refusing to add"
            )
        self._index.add(vecs)
        self._items.extend(items)

    def search(self, query_text: str, k: int) -> list[RetrievedItem]:
        """Return the top-k items by cosine similarity (descending).

        If `k > size`, returns all items. If the store is empty, returns
        the empty list — the `FlatVectorBaseline` relies on this to
        degenerate to no-memory when `supporting_session_ids` is empty.
        """
        if k <= 0:
            return []
        if self.size == 0:
            return []
        # Embed the query the same way items are embedded — but the
        # query text is whatever the baseline supplies (typically the
        # question text), NOT a role-tagged turn. The retrieval contract
        # is "find turns similar to the question", so no role prefix.
        q = self.embedder.embed([query_text])
        if q.dtype != np.float32:
            q = q.astype(np.float32, copy=False)
        eff_k = min(int(k), self.size)
        # FAISS returns (D, I) shaped (1, eff_k); D = inner products,
        # I = row indices. Already sorted descending by score.
        scores, idxs = self._index.search(q, eff_k)
        out: list[RetrievedItem] = []
        for rank, (score, idx) in enumerate(zip(scores[0], idxs[0])):
            if int(idx) < 0:
                # FAISS returns -1 for "no result" slots; possible at
                # eff_k > ntotal which we guard against, but defensive.
                continue
            out.append(
                RetrievedItem(
                    item=self._items[int(idx)],
                    score=float(score),
                    rank=rank,
                )
            )
        return out

    def clear(self) -> None:
        """Reset the index. Used between questions for fair comparison.

        See `NOTES/m1w3_design.md` §2.5 — per-question reset is the
        documented memory-persistence policy for the M1-W3 flat baseline.
        """
        self._index = self._new_index()
        self._items = []
