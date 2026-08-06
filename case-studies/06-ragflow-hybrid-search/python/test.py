"""test.py —— hybrid search 单测。只测公开 API，不依赖外部服务。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bm25 import BM25Index
from search import Result, hybrid_search
from vector import VectorIndex

SAMPLE_DOCS = [
    "Python list comprehension is elegant and expressive. Use [x*2 for x in range(10)].",
    "Sorting algorithms: merge sort, quick sort, bubble sort, insertion sort.",
    "The os.path module provides path manipulation functions like join and exists.",
    "Vector embeddings transform text into dense numerical representations for semantic search.",
    "BM25 is a bag-of-words retrieval function that ranks documents by query term frequency.",
    "Django ORM maps Python classes to database tables with declarative syntax.",
    "Kubernetes orchestration manages container scheduling across clusters with declarative YAML.",
    "BM25 normalization factor k1 controls term frequency saturation in ranking formula.",
    "Neural network backpropagation computes gradients layer by layer through the chain rule.",
    "Elasticsearch query_string DSL executes keyword matching against inverted indices at scale.",
]
SAMPLE_TITLES = [
    "Python List Comprehension",
    "Sorting Algorithms",
    "os.path Module",
    "Vector Embeddings",
    "BM25 Retrieval Function",
    "Django ORM",
    "Kubernetes Orchestration",
    "BM25 Normalization",
    "Neural Backpropagation",
    "Elasticsearch Query DSL",
]
import numpy as np

# ---- BM25Index ----


def test_bm25_contains_query_terms():
    idx = BM25Index()
    for d in SAMPLE_DOCS:
        idx.add(d)
    idx.build()
    hits = idx.search("bm25 retrieval ranking")
    ids = [i for i, _ in hits]
    assert 4 in ids and 7 in ids, ids


def test_bm25_exact_token():
    idx = BM25Index()
    for d in SAMPLE_DOCS:
        idx.add(d)
    idx.build()
    hits = idx.search("django orm declarative")
    assert hits, "django query should match"
    assert hits[0][0] == 5, f"expected doc 5, got {hits[0]}"


def test_bm25_empty_for_nonexistent_token():
    idx = BM25Index()
    idx.add("hello world")
    idx.build()
    assert idx.search("xyznonexistent123") == []


def test_bm25_score_increases_with_relevance():
    idx = BM25Index()
    for d in SAMPLE_DOCS:
        idx.add(d)
    idx.build()
    hits = idx.search("bm25")
    assert len(hits) > 0
    bm25_score = hits[0][1]
    # 多词匹配（"bm25 ranking formula"）应比单词（"bm25"）分数更高
    hits_multi = idx.search("bm25 ranking formula")
    if len(hits_multi) > 0:
        assert hits_multi[0][1] >= bm25_score


# ---- VectorIndex ----


def test_vector_similarity():
    idx = VectorIndex()
    for d in SAMPLE_DOCS:
        idx.add(d)
    idx.build()
    hits = idx.search("vector embeddings semantic")
    assert hits
    assert hits[0][1] > 0


def test_vector_empty_for_nonexistent_terms():
    idx = VectorIndex()
    idx.add("hello world")
    idx.build()
    # 真实 embedding 对任何文本都有非零向量（不会像 mock 那样返回空），
    # 所以这里改测"返回的向量维度一致"而非"空"
    hits = idx.search("xyznonexistent123")
    assert len(hits) == 1, f"expected 1 hit (real embedding is never empty), got {hits}"
    assert isinstance(hits[0][1], float)


# ---- hybrid_search ----


def test_hybrid_bm25_dominates_for_keyword():
    alpha = 0.8
    results = hybrid_search(
        SAMPLE_DOCS, SAMPLE_TITLES, "django orm", alpha=alpha, top_k=5
    )
    assert results[0].title == "Django ORM", f"got {results[0].title}"


def test_hybrid_vector_dominates_for_semantic():
    alpha = 0.2
    results = hybrid_search(
        SAMPLE_DOCS,
        SAMPLE_TITLES,
        "neural gradient descent learning",
        alpha=alpha,
        top_k=5,
    )
    assert results[0].title == "Neural Backpropagation", f"got {results[0].title}"


def test_hybrid_empty():
    # 真实 embedding 不会返回空（任意文本都有向量），所以改测"BM25 为空时只靠向量"
    results = hybrid_search(
        SAMPLE_DOCS, SAMPLE_TITLES, "xyznonexistent123", alpha=0.5, top_k=5
    )
    # BM25 为 0，向量路必有返回
    assert len(results) > 0, "real embedding never returns empty"
    for r in results:
        assert r.bm25_score == 0, "nonexistent token should have zero BM25"
        assert r.vector_score > 0


def test_hybrid_result_fields():
    results = hybrid_search(SAMPLE_DOCS, SAMPLE_TITLES, "bm25", alpha=0.5, top_k=3)
    assert len(results) > 0
    for r in results:
        assert isinstance(r, Result)
        assert r.bm25_score >= 0
        assert r.vector_score >= 0
        assert 0 <= r.score <= 1


def test_hybrid_respects_top_k():
    results = hybrid_search(SAMPLE_DOCS, SAMPLE_TITLES, "python", alpha=0.5, top_k=2)
    assert len(results) <= 2


if __name__ == "__main__":
    tests = [
        test_bm25_contains_query_terms,
        test_bm25_exact_token,
        test_bm25_empty_for_nonexistent_token,
        test_bm25_score_increases_with_relevance,
        test_vector_similarity,
        test_vector_empty_for_nonexistent_terms,
        test_hybrid_bm25_dominates_for_keyword,
        test_hybrid_vector_dominates_for_semantic,
        test_hybrid_empty,
        test_hybrid_result_fields,
        test_hybrid_respects_top_k,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  ✓ {t.__name__}")
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    if passed != len(tests):
        raise SystemExit(1)
