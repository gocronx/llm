"""search.py —— BM25 + 向量混合检索（RAGFlow 最小复刻）。

RAGFlow 的真实 BM25 委托给 ES/OS 倒排索引；本 demo 用纯 Python BM25，
让你看到底层在算什么。向量用内置 mock embedding（教学用）。

融合策略：BM25 和向量各自打分、min-max 归一、再加权求和。
"""

from __future__ import annotations

from dataclasses import dataclass

from bm25 import BM25Index
from vector import VectorIndex


@dataclass
class Result:
    title: str
    text: str
    score: float
    bm25_score: float
    vector_score: float


def _minmax_normalize(scores: list[float]) -> list[float]:
    """min-max 归一到 [0, 1]。"""
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [1.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


def hybrid_search(
    docs: list[str],
    titles: list[str],
    query: str,
    alpha: float = 0.5,
    top_k: int = 5,
) -> list[Result]:
    """
    BM25 + 向量混合检索。

    Args:
        docs: 文档列表
        titles: 文档标题列表
        query: 查询
        alpha: BM25 权重（1 - alpha = 向量权重）
        top_k: 返回数量
    """
    bm25_idx = BM25Index()
    vec_idx = VectorIndex()
    for d in docs:
        bm25_idx.add(d)
        vec_idx.add(d)
    bm25_idx.build()
    vec_idx.build()

    # 两路并行召回
    bm25_hits = bm25_idx.search(query, top_k=20)
    vec_hits = vec_idx.search(query, top_k=20)

    # doc_idx -> {bm25, vector}
    combined: dict[int, dict] = {}
    for idx, s in bm25_hits:
        combined.setdefault(idx, {"bm25": 0.0, "vector": 0.0})["bm25"] = s
    for idx, s in vec_hits:
        combined.setdefault(idx, {"bm25": 0.0, "vector": 0.0})["vector"] = s

    # 两路各自归一后加权
    bm25_scores = [v["bm25"] for v in combined.values()]
    vector_scores = [v["vector"] for v in combined.values()]
    bm25_norm = dict(zip(combined.keys(), _minmax_normalize(bm25_scores)))
    vector_norm = dict(zip(combined.keys(), _minmax_normalize(vector_scores)))

    results = []
    for idx, vals in combined.items():
        fused = alpha * bm25_norm[idx] + (1 - alpha) * vector_norm[idx]
        results.append(
            Result(
                title=titles[idx] if idx < len(titles) else f"doc-{idx}",
                text=docs[idx][:120] + "..." if len(docs[idx]) > 120 else docs[idx],
                score=fused,
                bm25_score=vals["bm25"],
                vector_score=vals["vector"],
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]
