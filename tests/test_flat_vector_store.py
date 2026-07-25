"""Tests for the FAISS-backed flat vector store (M1-W3 §3.2).

Three contracts:
  1. Round-trip — adding turn #X and searching with the text of turn #X
     verbatim returns turn #X at top-1 with similarity ≈ 1.0. This is the
     "search for own text" sanity check from §3.2.
  2. Clear — `clear()` resets search results to empty.
  3. Top-k with k > store size returns all items, no exception.

Tests run against the hermetic `FakeEmbedder` (sha256-based) so they do
not need torch / sentence-transformers. The integration with the real
MiniLM weights is exercised by `test_embeddings.py::test_turn_embedder_real_minilm_smoke`.
"""

from __future__ import annotations

import pytest

from ask.baselines.embeddings import FakeEmbedder
from ask.baselines.flat_vector_store import (
    FlatVectorStore,
    MemoryItem,
    RetrievedItem,
)

# Skip the whole module if faiss-cpu is not importable. The pyproject
# `[ml]` group declares it; this guard is for bare CI envs.
faiss = pytest.importorskip("faiss")


def _make_items(n: int) -> list[MemoryItem]:
    """Build n distinct memory items with role-alternating turns."""
    out: list[MemoryItem] = []
    for i in range(n):
        out.append(
            MemoryItem(
                text=f"item-{i:03d} content body {i}",
                role="user" if i % 2 == 0 else "assistant",
                session_id=f"sess-{i // 5}",
                turn_idx=i,
                timestamp=None,
            )
        )
    return out


# --------------------------------------------------------------------- #
# §3.2 contract tests                                                    #
# --------------------------------------------------------------------- #


def test_store_starts_empty() -> None:
    s = FlatVectorStore(embedder=FakeEmbedder(embedding_dim=32))
    assert s.size == 0
    assert s.search("anything", k=5) == []


def test_search_for_own_text_returns_self_at_top1() -> None:
    """Add 100 turns, search with the exact text of turn #42, expect #42 at rank 0.

    This is the canonical sanity check the §3.2 task spec calls for.
    Similarity must be ≈ 1.0 (FakeEmbedder is deterministic and the same
    string hashes to the same vector).
    """
    s = FlatVectorStore(embedder=FakeEmbedder(embedding_dim=64))
    items = _make_items(100)
    s.add(items)
    assert s.size == 100

    # Search using the exact embed-text of item #42.
    target = items[42]
    query = target.embed_text()
    results = s.search(query, k=5)
    assert len(results) == 5
    top = results[0]
    assert top.item.turn_idx == 42, "expected item-42 at rank 0"
    assert top.rank == 0
    # Cosine of identical vectors is 1.0; allow float32 tolerance.
    assert top.score == pytest.approx(1.0, abs=1e-5)


def test_search_with_k_greater_than_size_returns_all() -> None:
    """k > size must NOT raise. Returns all items, sorted by descending score."""
    s = FlatVectorStore(embedder=FakeEmbedder(embedding_dim=32))
    s.add(_make_items(3))
    out = s.search("query text", k=10)
    assert len(out) == 3
    # Sorted descending by score.
    scores = [r.score for r in out]
    assert scores == sorted(scores, reverse=True)
    # Ranks are 0, 1, 2 in order.
    assert [r.rank for r in out] == [0, 1, 2]


def test_clear_returns_search_to_empty() -> None:
    """`clear()` is the per-question reset documented in §2.5 of the design note."""
    s = FlatVectorStore(embedder=FakeEmbedder(embedding_dim=32))
    s.add(_make_items(10))
    assert s.size == 10
    s.clear()
    assert s.size == 0
    assert s.search("anything", k=3) == []
    # And still adds correctly post-clear (re-use across questions).
    s.add(_make_items(5))
    assert s.size == 5


def test_search_with_k_zero_returns_empty() -> None:
    """k=0 is a defensive degenerate path."""
    s = FlatVectorStore(embedder=FakeEmbedder(embedding_dim=16))
    s.add(_make_items(3))
    assert s.search("q", k=0) == []


def test_search_with_negative_k_returns_empty() -> None:
    s = FlatVectorStore(embedder=FakeEmbedder(embedding_dim=16))
    s.add(_make_items(3))
    assert s.search("q", k=-5) == []


def test_add_empty_list_is_a_noop() -> None:
    s = FlatVectorStore(embedder=FakeEmbedder(embedding_dim=16))
    s.add([])
    assert s.size == 0


def test_dim_mismatch_raises_on_add() -> None:
    """A wrong-dim embedder must fail loudly — silently storing garbage breaks every result."""
    s = FlatVectorStore(embedder=FakeEmbedder(embedding_dim=32))

    # Build a store keyed at dim=32, then try to add via a 16-dim embedder
    # by swapping the underlying embedder (simulates a misconfiguration).
    s.embedder = FakeEmbedder(embedding_dim=16)
    with pytest.raises(ValueError, match="dim="):
        s.add(_make_items(2))


def test_index_is_indexflatip_by_default() -> None:
    """Pin the index choice; an upgrade to IVF/HNSW must change a test."""
    s = FlatVectorStore(embedder=FakeEmbedder(embedding_dim=32))
    # FAISS index types expose their kind via __class__.__name__.
    assert s._index.__class__.__name__ == "IndexFlatIP"  # noqa: SLF001


def test_retrieved_item_to_dict_is_serializable() -> None:
    """`judgments.jsonl` round-trips RetrievedItem records — must serialize."""
    item = MemoryItem(text="hi", role="user", session_id="s1", turn_idx=0)
    r = RetrievedItem(item=item, score=0.987, rank=0)
    d = r.to_dict()
    import json

    json.dumps(d)  # must not raise
    assert d["item"]["text"] == "hi"
    assert d["score"] == pytest.approx(0.987)
    assert d["rank"] == 0


def test_results_descend_by_score() -> None:
    """Top-k results must be sorted by inner product, descending."""
    s = FlatVectorStore(embedder=FakeEmbedder(embedding_dim=64))
    items = _make_items(50)
    s.add(items)

    # Use an arbitrary query text that's not equal to any item's text.
    out = s.search("a query nobody embedded yet", k=10)
    scores = [r.score for r in out]
    assert scores == sorted(scores, reverse=True)
    # Ranks reflect descending order.
    assert [r.rank for r in out] == list(range(len(out)))


def test_size_and_internal_index_agree() -> None:
    s = FlatVectorStore(embedder=FakeEmbedder(embedding_dim=32))
    s.add(_make_items(7))
    assert s.size == 7
    assert int(s._index.ntotal) == 7  # noqa: SLF001
    s.clear()
    assert s.size == 0
    assert int(s._index.ntotal) == 0  # noqa: SLF001


def test_memory_item_is_frozen() -> None:
    """Mutation must raise — a desynced metadata list breaks every search."""
    import dataclasses

    item = MemoryItem(text="x", role="user", session_id="s", turn_idx=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.text = "mutated"  # type: ignore[misc]
