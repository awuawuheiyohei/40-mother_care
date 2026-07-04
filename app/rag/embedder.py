"""Embedding client.

Real mode: POSTs to OpenAI-compatible /v1/embeddings.
Mock mode: deterministic hash-based vectors, normalized. NOT real embeddings —
just stable vectors that make the retrieval pipeline testable end-to-end.
"""

from __future__ import annotations

import hashlib

import httpx
import numpy as np

from app.config import get_settings


class Embedder:
    def __init__(self, base_url: str, api_key: str, model: str, dim: int, mock: bool):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dim = dim
        self.mock = mock

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)

        if self.mock:
            return self._mock_embed(texts)

        return self._real_embed(texts)

    def _real_embed(self, texts: list[str]) -> np.ndarray:
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "input": texts}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        vectors = np.array([d["embedding"] for d in data["data"]], dtype=np.float32)
        # L2 normalize for cosine similarity
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms

    def _mock_embed(self, texts: list[str]) -> np.ndarray:
        """Deterministic mock embedding.

        Same text always gets same vector. Good enough to test the pipeline
        but retrieval quality will be poor — switch to real embeddings ASAP.
        """
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            # Use SHA-256 to generate a stable stream of bytes
            digest = hashlib.sha256(t.encode("utf-8")).digest()
            # Repeat digest to fill `dim` bytes
            buf = (digest * ((self.dim // len(digest)) + 1))[: self.dim]
            # Interpret bytes as ints in [0, 255], center & scale to ~[-1, 1]
            arr = np.frombuffer(buf, dtype=np.uint8).astype(np.float32)
            arr = (arr - 127.5) / 127.5  # now in [-1, 1] deterministically
            out[i] = arr
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return (out / norms).astype(np.float32)


def get_embedder() -> Embedder:
    s = get_settings()
    return Embedder(
        base_url=s.embed_base_url,
        api_key=s.embed_api_key,
        model=s.embed_model,
        dim=s.embed_dim,
        mock=not s.embed_configured,
    )


if __name__ == "__main__":
    e = get_embedder()
    v = e.embed(["新生儿黄疸", "宝宝发烧怎么办"])
    print(f"mock={e.mock}, shape={v.shape}, norms={np.linalg.norm(v, axis=1)}")