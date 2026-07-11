"""Memory-baseline implementations.

The four LongMemEval baselines share a single `BaselineAnswer` shape so the
evaluator (`ksa.eval.longmemeval`) is generic across them. This is what makes
Week 3's flat-vector and Week 4's recency / naive-overwrite baselines mostly
prompt + retrieval engineering, not framework engineering.
"""

from .base import BaselineAnswer
from .embeddings import (
    Embedder,
    FakeEmbedder,
    OllamaEmbedder,
    OpenAICompatibleEmbedder,
    TurnEmbedder,
    role_tag,
)
from .flat_vector import FlatVectorBaseline, build_session_corpus
from .flat_vector_store import FlatVectorStore, MemoryItem, RetrievedItem
from .no_memory import NoMemoryBaseline
from .recency_pruning import (
    RecencyPruningBaseline,
    TrivialExtractedItem,
    build_session_corpus_for_recency,
    trivial_extract,
)

__all__ = [
    "BaselineAnswer",
    "NoMemoryBaseline",
    "NaiveOverwriteBaseline",
    # M1-W3 — flat-vector baseline:
    "FlatVectorBaseline",
    "FlatVectorStore",
    "MemoryItem",
    "RetrievedItem",
    "Embedder",
    "FakeEmbedder",
    "OllamaEmbedder",
    "OpenAICompatibleEmbedder",
    "TurnEmbedder",
    "role_tag",
    "build_session_corpus",
    # M1-W4 — recency-pruning baseline:
    "RecencyPruningBaseline",
    "TrivialExtractedItem",
    "trivial_extract",
    "build_session_corpus_for_recency",
]


def __getattr__(name: str):
    if name == "NaiveOverwriteBaseline":
        from .naive_overwrite import NaiveOverwriteBaseline

        return NaiveOverwriteBaseline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
