"""Retriever: combine FAISS cosine score with source-priority boost.

The boost model is intentionally simple — multiply cosine similarity by the
source's authoritative weight, then rerank. A real cross-encoder reranker
would be more accurate but adds latency and an extra model.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.kb import KnowledgeItem
from app.rag.embedder import Embedder
from app.rag.vector_store import FaissStore


@dataclass
class RetrievalHit:
    item: KnowledgeItem
    score: float          # post-boost final score
    raw_score: float      # pre-boost cosine similarity
    boost: float          # source weight applied


class Retriever:
    def __init__(
        self,
        embedder: Embedder,
        store: FaissStore,
        source_weights: dict[str, float],
        min_score: float,
        top_k: int,
    ):
        self.embedder = embedder
        self.store = store
        self.source_weights = source_weights
        self.min_score = min_score
        self.top_k = top_k

    def retrieve(self, query: str) -> list[RetrievalHit]:
        if self.store.size == 0:
            return []
        q_vec = self.embedder.embed([query])
        raw_hits = self.store.search(q_vec, self.top_k)
        results: list[RetrievalHit] = []
        for raw_score, item in raw_hits:
            boost = self.source_weights.get(item.source, 0.5)
            final = raw_score * boost
            if final < self.min_score:
                continue
            results.append(RetrievalHit(item=item, score=final, raw_score=raw_score, boost=boost))
        results.sort(key=lambda h: h.score, reverse=True)
        return results


_retriever_singleton: Retriever | None = None


def get_retriever() -> Retriever:
    """Lazy singleton. Assumes the index has been built (run scripts/seed_kb.py + build_index)."""
    global _retriever_singleton
    if _retriever_singleton is not None:
        return _retriever_singleton

    s = get_settings()
    from pathlib import Path
    if not Path(s.rag_index_path).exists():
        raise FileNotFoundError(
            f"FAISS index not found at {s.rag_index_path}. "
            "Run: python scripts/seed_kb.py && python -m app.rag.build_index"
        )

    from app.rag.embedder import get_embedder
    from app.rag.vector_store import FaissStore

    store = FaissStore.load(s.rag_index_path, dim=s.embed_dim)
    embedder = get_embedder()
    _retriever_singleton = Retriever(
        embedder=embedder,
        store=store,
        source_weights=s.source_weights,
        min_score=s.rag_min_score,
        top_k=s.rag_top_k,
    )
    return _retriever_singleton


def reset_retriever() -> None:
    """Drop singleton. Used in tests."""
    global _retriever_singleton
    _retriever_singleton = None