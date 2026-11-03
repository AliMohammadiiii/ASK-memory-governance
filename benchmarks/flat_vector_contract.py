"""Small reproducible exact-retrieval comparison; no model or dataset required."""

from __future__ import annotations

import json
import time

import numpy as np

from ask.baselines.flat_vector_store import _NumpyFlatIPIndex


def main() -> None:
    rng = np.random.default_rng(20261103)
    vectors = rng.normal(size=(1500, 384)).astype(np.float32)
    queries = rng.normal(size=(32, 384)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    queries /= np.linalg.norm(queries, axis=1, keepdims=True)
    k = 10

    numpy_index = _NumpyFlatIPIndex(vectors.shape[1])
    numpy_index.add(vectors)
    start = time.perf_counter()
    numpy_results = [numpy_index.search(query[None, :], k) for query in queries]
    numpy_ms = (time.perf_counter() - start) * 1000 / len(queries)

    result: dict[str, object] = {
        "seed": 20261103,
        "vectors": len(vectors),
        "dimension": vectors.shape[1],
        "queries": len(queries),
        "k": k,
        "numpy_ms_per_query": round(numpy_ms, 4),
    }
    try:
        import faiss
    except ImportError:
        result["faiss"] = "not installed; comparison omitted"
    else:
        faiss_index = faiss.IndexFlatIP(vectors.shape[1])
        faiss_index.add(vectors)
        start = time.perf_counter()
        faiss_results = [faiss_index.search(query[None, :], k) for query in queries]
        faiss_ms = (time.perf_counter() - start) * 1000 / len(queries)
        scores_match = all(
            np.allclose(numpy[0], faiss_result[0], rtol=0, atol=2e-6)
            for numpy, faiss_result in zip(numpy_results, faiss_results, strict=True)
        )
        rows_match = all(
            np.array_equal(numpy[1], faiss_result[1])
            for numpy, faiss_result in zip(numpy_results, faiss_results, strict=True)
        )
        result.update(
            faiss_ms_per_query=round(faiss_ms, 4),
            score_parity=scores_match,
            row_parity=rows_match,
        )
        if not scores_match or not rows_match:
            raise RuntimeError("NumPy and FAISS results differ on the seeded workload")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
