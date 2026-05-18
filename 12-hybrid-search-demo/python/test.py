"""test.py —— 在 sample_code/ 上跑确定性测试，不依赖外网。"""
from __future__ import annotations

from pathlib import Path

from search import VectorIndex, grep_search, hybrid_search

ROOT = Path(__file__).parent / "sample_code"


def test_grep_finds_keyword() -> bool:
    """grep 应该能精确找到 'login' 这种字面 token。"""
    hits = grep_search(ROOT, "login")
    ok = len(hits) >= 1 and any("auth" in h.file_path for h in hits)
    print(f"{'✓' if ok else '✗'} grep finds 'login' ({len(hits)} hits)")
    return ok


def test_vector_semantic_match() -> bool:
    """vector 应该能用语义 'authenticate' 找到 auth.py 即使代码里用的是 'login'。"""
    vidx = VectorIndex(ROOT).build()
    hits = vidx.search("authenticate user", top_k=5)
    ok = len(hits) >= 1 and any("auth" in h.file_path for h in hits[:3])
    print(f"{'✓' if ok else '✗'} vector semantic match (top files: {[h.file_path for h in hits[:3]]})")
    return ok


def test_hybrid_combines() -> bool:
    """hybrid 同时考虑 grep 和 vector，alpha=0.4 时两边都有信号的应该排前面。"""
    vidx = VectorIndex(ROOT).build()
    hits = hybrid_search(ROOT, vidx, "database connection", alpha=0.4)
    ok = len(hits) >= 1 and any("database" in h.file_path for h in hits[:3])
    print(f"{'✓' if ok else '✗'} hybrid finds 'database connection' (top: {[h.file_path for h in hits[:3]]})")
    return ok


def main() -> None:
    passed = sum([test_grep_finds_keyword(), test_vector_semantic_match(), test_hybrid_combines()])
    print(f"\n{passed}/3 passed")


if __name__ == "__main__":
    main()
