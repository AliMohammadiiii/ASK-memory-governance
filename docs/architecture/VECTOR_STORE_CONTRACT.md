# Flat vector retrieval contract

`FlatVectorStore` performs exact search with FAISS `IndexFlatIP` when FAISS is
installed, and an exact NumPy inner-product scan otherwise. The store validates
the configured dimension, rejects non-finite and zero vectors, and L2-normalizes
both stored vectors and queries. Returned inner products therefore represent
cosine similarity, subject to float32 rounding.

Results sort by descending score. Exact score ties resolve by insertion index,
including ties at the top-k boundary. The NumPy implementation uses a stable
sort. FAISS results are ordered by the same secondary key, and a boundary tie
causes an exhaustive result request before truncation. Duplicate memory items
remain distinct rows; no identity-based deduplication is performed. An empty
store or non-positive `k` returns no results.

The relevant conformance checks are `tests/test_numpy_flat_index_contract.py`
and `tests/test_flat_vector_store.py`. The latter requires optional `faiss-cpu`;
report parity only when it has run in an environment with FAISS installed.
One seeded synthetic run measured 0.1442 ms/query for NumPy and 0.1640
ms/query for FAISS on a 1,500 x 384 vector index, 32 queries, and k=10. It ran
on Python 3.12.14, macOS arm64, with score and row parity true. These are a
single local measurement, not a throughput guarantee. Reproduce with:

```bash
uv run --isolated --with '.[dev]' --with 'faiss-cpu>=1.8,<2' python benchmarks/flat_vector_contract.py
```
