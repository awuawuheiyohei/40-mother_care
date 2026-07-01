"""FAISS-backed vector store.

Stores normalized embeddings in IndexFlatIP (inner product = cosine sim
when vectors are L2-normalized). We also keep an id->KB-item map so we can
look up metadata on hit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import faiss
import numpy as np

from app.kb import KnowledgeItem


@dataclass
class IndexedKB:
    """Map from index position -> KnowledgeItem."""

    items: list[KnowledgeItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"items": [json.loads(item.model_dump_json()) for item in self.items]}

    @classmethod
    def from_dict(cls, d: dict) -> "IndexedKB":
        return cls(items=[KnowledgeItem(**x) for x in d["items"]])


class FaissStore:
    def __init__(self, dim: int):
        self.dim = dim
        # IndexFlatIP = inner product. With L2-normalized vectors, IP == cosine sim.
        self.index: faiss.IndexFlatIP = faiss.IndexFlatIP(dim)
        self.kb = IndexedKB()

    @property
    def size(self) -> int:
        return self.index.ntotal

    def add(self, vectors: np.ndarray, items: list[KnowledgeItem]) -> None:
        assert vectors.shape[0] == len(items), "vector/item count mismatch"
        assert vectors.shape[1] == self.dim, f"expected dim={self.dim}, got {vectors.shape[1]}"
        self.index.add(vectors.astype(np.float32))
        self.kb.items.extend(items)

    def search(self, query_vec: np.ndarray, top_k: int) -> list[tuple[float, KnowledgeItem]]:
        if self.size == 0:
            return []
        k = min(top_k, self.size)
        scores, ids = self.index.search(query_vec.astype(np.float32), k)
        hits: list[tuple[float, KnowledgeItem]] = []
        for score, idx in zip(scores[0].tolist(), ids[0].tolist()):
            if idx < 0 or idx >= len(self.kb.items):
                continue
            hits.append((float(score), self.kb.items[idx]))
        return hits

    def save(self, index_path: str | Path, meta_path: str | Path | None = None) -> None:
        index_path = Path(index_path)
        faiss.write_index(self.index, str(index_path))
        meta_path = meta_path or index_path.with_suffix(".meta.json")
        with Path(meta_path).open("w", encoding="utf-8") as f:
            json.dump(self.kb.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, index_path: str | Path, meta_path: str | Path | None = None, dim: int = 0) -> "FaissStore":
        index_path = Path(index_path)
        if not index_path.exists():
            raise FileNotFoundError(f"FAISS index not found at {index_path}")
        index = faiss.read_index(str(index_path))
        store = cls(dim=index.d)
        store.index = index
        meta_path = meta_path or index_path.with_suffix(".meta.json")
        if Path(meta_path).exists():
            with Path(meta_path).open("r", encoding="utf-8") as f:
                store.kb = IndexedKB.from_dict(json.load(f))
        return store