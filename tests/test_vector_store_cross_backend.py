from __future__ import annotations

import numpy as np
import pytest

from ask.baselines.flat_vector_store import (
    FlatVectorStore,
    MemoryItem,
    _NumpyFlatIPIndex,
)

faiss = pytest.importorskip("faiss")


class RepeatedVectorEmbedder:
    embedding_dim = 2

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.tile(np.asarray([[3.0, 4.0]], dtype=np.float32), (len(texts), 1))


def _item(index: int) -> MemoryItem:
    return MemoryItem(text=f"item-{index}", role="user", session_id="s", turn_idx=index)


@pytest.mark.parametrize("backend", ["faiss", "numpy"])
def test_top_k_boundary_ties_choose_earliest_insertion(backend: str) -> None:
    store = FlatVectorStore(embedder=RepeatedVectorEmbedder())  # type: ignore[arg-type]
    if backend == "numpy":
        store._index = _NumpyFlatIPIndex(2)  # noqa: SLF001
    store.add([_item(0), _item(1), _item(2)])

    result = store.search("query", k=1)

    assert [item.item.turn_idx for item in result] == [0]
    assert result[0].score == pytest.approx(1.0, abs=1e-6)
