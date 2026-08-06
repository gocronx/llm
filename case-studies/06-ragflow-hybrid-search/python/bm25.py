"""bm25.py —— BM25Index：纯 Python BM25，可独立使用。"""

from __future__ import annotations

import math

from tokenizer import tokenize


class BM25Index:
    """纯 Python BM25，可独立使用。

    Args:
        k1: 词频饱和度参数（默认 1.5）
        b: 文档长度归一化参数（默认 0.75）
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: list[str] = []
        self._tf: list[dict[str, int]] = []
        self._df: dict[str, int] = {}
        self._avgdl: float = 0.0

    def add(self, text: str) -> None:
        tokens = tokenize(text)
        self.docs.append(text)
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
            self._df[t] = self._df.get(t, 0) + 1
        self._tf.append(tf)
        n = len(self.docs)
        if n > 1:
            self._avgdl = self._avgdl * (n - 1) / n + len(tokens) / n
        else:
            self._avgdl = len(tokens)

    def build(self) -> "BM25Index":
        return self

    def _idf(self, token: str) -> float:
        n = len(self.docs)
        df = self._df.get(token, 0)
        if df == 0:
            return 0.0
        return math.log((n - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, text: str, doc_idx: int) -> float:
        tokens = tokenize(text)
        tf = self._tf[doc_idx]
        dl = len(self.docs[doc_idx])
        result = 0.0
        for token in set(tokens):
            idf = self._idf(token)
            if idf == 0:
                continue
            freq = tf.get(token, 0)
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (1 - self.b + self.b * dl / self._avgdl)
            result += idf * numerator / denominator
        return result

    def search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        """返回 [(doc_idx, bm25_score), ...]，按分数降序。"""
        results = []
        for i in range(len(self.docs)):
            s = self.score(query, i)
            if s > 0:
                results.append((i, s))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
