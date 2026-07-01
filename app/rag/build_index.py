"""Build the FAISS index from KB. Run: python -m app.rag.build_index"""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.kb.loader import iter_embedding_inputs, load_kb
from app.rag.embedder import get_embedder
from app.rag.vector_store import FaissStore


def main() -> None:
    s = get_settings()
    items = load_kb(s.rag_kb_path)
    if not items:
        raise SystemExit(f"No KB items found in {s.rag_kb_path}. Add a *.jsonl file first.")

    print(f"[build_index] loaded {len(items)} KB items")

    embedder = get_embedder()
    print(f"[build_index] embedder mode: {'MOCK' if embedder.mock else 'REAL'} ({embedder.model})")

    ids_texts = iter_embedding_inputs(items)
    texts = [t for _, t in ids_texts]
    vectors = embedder.embed(texts)
    print(f"[build_index] embedded {vectors.shape[0]} vectors of dim {vectors.shape[1]}")

    store = FaissStore(dim=s.embed_dim)
    store.add(vectors, items)
    store.save(s.rag_index_path)
    print(f"[build_index] saved index -> {s.rag_index_path}")
    print(f"[build_index] saved meta  -> {Path(s.rag_index_path).with_suffix('.meta.json')}")


if __name__ == "__main__":
    main()