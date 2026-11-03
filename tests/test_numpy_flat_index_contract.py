from __future__ import annotations

import numpy as np

from ask.baselines.flat_vector_store import _NumpyFlatIPIndex


def test_numpy_flat_index_orders_equal_scores_by_insertion_index() -> None:
    index = _NumpyFlatIPIndex(2)
    index.add(np.asarray([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=np.float32))

    scores, rows = index.search(np.asarray([[1.0, 0.0]], dtype=np.float32), 2)

    assert rows.tolist() == [[0, 1]]
    assert scores.tolist() == [[1.0, 1.0]]
