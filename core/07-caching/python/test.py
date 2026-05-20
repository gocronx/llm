"""test.py —— 纯逻辑测试，不调 LLM。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from cache import Exact, Semantic


def test_exact_hit() -> bool:
    c = Exact()
    c.set("hi", "你好")
    ok = c.get("hi") == "你好" and c.get("Hi") is None
    print(f"{'✓' if ok else '✗'} exact: case-sensitive miss")
    return ok


def test_exact_persist() -> bool:
    with tempfile.TemporaryDirectory() as d:
        p = str(Path(d) / "c.json")
        c1 = Exact(p)
        c1.set("k", "v")
        c2 = Exact(p)  # 新实例读盘
        ok = c2.get("k") == "v"
    print(f"{'✓' if ok else '✗'} exact: persists to disk")
    return ok


def test_semantic_near_hit() -> bool:
    c = Semantic(threshold=0.5)
    c.set("Python 是什么编程语言", "通用解释型语言")
    # 仅多了标点的近似问法应该命中
    hit = c.get("Python 是什么编程语言？")
    ok = hit is not None
    print(f"{'✓' if ok else '✗'} semantic: punctuation-variant hits ({hit!r})")
    return ok


def test_semantic_unrelated_miss() -> bool:
    c = Semantic(threshold=0.7)
    c.set("什么是 Python", "Python 是...")
    # 完全不相干的问题应该 miss
    miss = c.get("今天天气怎么样")
    ok = miss is None
    print(f"{'✓' if ok else '✗'} semantic: unrelated question misses")
    return ok


def main() -> None:
    passed = sum([test_exact_hit(), test_exact_persist(),
                  test_semantic_near_hit(), test_semantic_unrelated_miss()])
    print(f"\n{passed}/4 passed")


if __name__ == "__main__":
    main()
