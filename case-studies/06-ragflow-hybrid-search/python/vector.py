"""vector.py —— 向量检索。

优先用 EmbeddingClient 调真实 /embeddings 接口；无 API 配置时降级到
内置 MockEmbedder（word TF + cosine）。
"""

from __future__ import annotations

import numpy as np
from embeddings import EmbeddingClient, get_client
from tokenizer import tokenize


class MockEmbedder:
    """教学用 embedder：word TF 向量 + cosine 相似度。"""

    def __init__(self, dim: int = 256):
        self.dim = dim
        self._vocab: dict[str, int] = {}
        self._next = 0

    def _token_pos(self, token: str) -> int:
        if token not in self._vocab:
            self._vocab[token] = self._next
            self._next += 1
        return self._vocab[token]

    def _to_vector(self, text: str) -> np.ndarray:
        tokens = tokenize(text)
        vec = np.zeros(min(self.dim, len(self._vocab) + len(tokens)))
        for t in tokens:
            pos = self._token_pos(t)
            if pos < vec.size:
                vec[pos] += 1
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def embed(self, text: str) -> np.ndarray:
        return self._to_vector(text.lower())

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        return np.array([self.embed(t) for t in texts])


class EmbedderAdapter:
    """统一 embed/embed_batch 接口，优先真实 API，否则 mock。"""

    def __init__(self, dim: int = 256):
        self._real = get_client()
        self._mock = MockEmbedder(dim)
        self._use_real = bool(self._real)

    @property
    def dimension(self) -> int:
        if self._use_real:
            return 1024  # text-embedding-bge-large-zh-v1.5
        return 256

    def embed(self, text: str) -> np.ndarray:
        if self._use_real:
            vec = self._real.embed(text)
            if vec is not None:
                return vec
        return self._mock.embed(text)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        if self._use_real:
            vecs = self._real.embed_batch(texts)
            if vecs is not None:
                return vecs
        return self._mock.embed_batch(texts)


class VectorIndex:
    """构建一次索引，反复查询。真实 API 返回固定维度，cosine 直接算。"""

    def __init__(self, dim: int = 256):
        self.embedder = EmbedderAdapter(dim)
        self._vectors: np.ndarray = np.array([])
        self.docs: list[str] = []
        self._use_real = bool(self.embedder._use_real)

    def add(self, text: str) -> None:
        self.docs.append(text)

    def build(self) -> "VectorIndex":
        vecs = [self.embedder.embed(t) for t in self.docs]
        self._vectors = np.array(vecs)
        return self

    def search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        """返回 [(doc_idx, cosine_sim), ...]，按相似度降序。"""
        if self._vectors.size == 0:
            return []
        qv = self.embedder.embed(query)
        sims = (qv @ self._vectors.T).flatten()
        idx = sims.argsort()[::-1][:top_k]
        return [(i, float(sims[i])) for i in idx if sims[i] > 0]
