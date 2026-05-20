"""main.py —— demo only：在 sample_code/ 上跑 grep / vector / hybrid 三种检索。"""
from __future__ import annotations

from pathlib import Path

from search import VectorIndex, grep_search, hybrid_search

ROOT = Path(__file__).parent / "sample_code"

QUERIES = [
    "login function",            # 精确符号
    "how to authenticate user",  # 语义
    "database connection",       # 混合
]


def show(title: str, hits: list, limit: int = 5) -> None:
    print(f"\n[{title}]")
    if not hits:
        print("  (no hits)")
        return
    for h in hits[:limit]:
        print(f"  {h.score:.3f}  grep={h.grep_score:.2f} vec={h.vector_score:.3f}  "
              f"{h.file_path}  {h.snippet[:60]}")


def main() -> None:
    vidx = VectorIndex(ROOT).build()
    print(f"建索引：{len(vidx.docs)} 个 chunk")

    for q in QUERIES:
        print(f"\n=== query: {q!r} ===")
        show("grep", grep_search(ROOT, q))
        show("vector", vidx.search(q))
        show("hybrid (alpha=0.4)", hybrid_search(ROOT, vidx, q, alpha=0.4))


if __name__ == "__main__":
    main()
