"""main.py —— 交互式混合检索 demo。"""

from search import hybrid_search

DOCS = [
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
TITLES = [
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


def demo(query: str, alpha: float = 0.5) -> None:
    print(f"\n查询: {query}  (BM25 权重 alpha={alpha})")
    print("-" * 60)
    results = hybrid_search(DOCS, TITLES, query, alpha=alpha, top_k=5)
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r.title}]  (score={r.score:.3f})")
        print(f"     BM25={r.bm25_score:.3f}  vector={r.vector_score:.3f}")
        print(f"     {r.text}")


if __name__ == "__main__":
    demo("django orm", alpha=0.8)
    demo("neural gradient descent learning", alpha=0.2)
    demo("bm25 ranking formula", alpha=0.5)
