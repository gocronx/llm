"""search.py —— 三种代码检索：grep / vector(TF-IDF) / hybrid。整文件 cp 进项目即可。

为什么用 hybrid：grep 命中精确符号（"def login"）但不懂语义；vector
懂语义（"how to authenticate" → auth.py）但精确符号反而错位。两个分数
加权融合既不漏精确也不漏意图。

向量用 TF-IDF（字符 + token 双特征）不用 embedding —— 不引大依赖，效
果上对小代码库已经够；生产里换 sentence-transformers / OpenAI embedding。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


CODE_EXT = (".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".h")


@dataclass
class Hit:
    file_path: str
    snippet: str
    score: float
    grep_score: float = 0.0
    vector_score: float = 0.0


def _iter_files(root: Path):
    for f in root.rglob("*"):
        if f.is_file() and f.suffix in CODE_EXT:
            yield f


# ---- Grep：每行匹配，关键词命中比例 ----

def grep_search(root: Path, query: str, max_results: int = 50) -> list[Hit]:
    keywords = [w for w in query.lower().split() if len(w) > 1]
    if not keywords:
        return []
    hits: list[Hit] = []
    for f in _iter_files(root):
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            low = line.lower()
            n_hit = sum(1 for k in keywords if k in low)
            if n_hit:
                score = n_hit / len(keywords)
                hits.append(Hit(file_path=f"{f.name}:{i}",
                                snippet=line.strip(), score=score, grep_score=score))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:max_results]


# ---- Vector：把所有代码切 chunk，TF-IDF 向量化，cosine ----

class VectorIndex:
    """构建一次索引，反复查询。chunks 是 chunk_size 字符为单位的滑窗。"""
    def __init__(self, root: Path, chunk_size: int = 400):
        self.root = root
        self.chunk_size = chunk_size
        self.docs: list[tuple[str, str]] = []  # (file_path, chunk)
        # TF-IDF：1-2gram 字符 + 单词 token，兼顾中文和英文
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), max_features=5000)
        self._mat = None

    def build(self) -> "VectorIndex":
        for f in _iter_files(self.root):
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            for i in range(0, len(text), self.chunk_size):
                self.docs.append((f.name, text[i:i + self.chunk_size]))
        self._mat = self.vec.fit_transform([d for _, d in self.docs])
        return self

    def search(self, query: str, top_k: int = 20) -> list[Hit]:
        if self._mat is None:
            raise RuntimeError("call build() first")
        qv = self.vec.transform([query])
        sims = cosine_similarity(qv, self._mat).flatten()
        idx = sims.argsort()[::-1][:top_k]
        return [Hit(file_path=self.docs[i][0], snippet=self.docs[i][1][:200],
                    score=float(sims[i]), vector_score=float(sims[i]))
                for i in idx if sims[i] > 0]


# ---- Hybrid：grep score * alpha + vector score * (1-alpha) ----

def hybrid_search(root: Path, vector_index: VectorIndex, query: str,
                  alpha: float = 0.4, top_k: int = 10) -> list[Hit]:
    """alpha=0.4 偏向语义，0.6 偏向精确符号。按文件聚合后取 top_k。"""
    by_file: dict[str, Hit] = {}
    for h in grep_search(root, query):
        agg = by_file.setdefault(h.file_path.split(":")[0],
                                  Hit(file_path=h.file_path.split(":")[0], snippet="",
                                      score=0, grep_score=0, vector_score=0))
        agg.grep_score = max(agg.grep_score, h.grep_score)
        if not agg.snippet:
            agg.snippet = h.snippet
    for h in vector_index.search(query, top_k=20):
        agg = by_file.setdefault(h.file_path,
                                  Hit(file_path=h.file_path, snippet=h.snippet,
                                      score=0, grep_score=0, vector_score=0))
        agg.vector_score = max(agg.vector_score, h.vector_score)
        if not agg.snippet:
            agg.snippet = h.snippet
    # 融合
    for h in by_file.values():
        h.score = alpha * h.grep_score + (1 - alpha) * h.vector_score
    return sorted(by_file.values(), key=lambda h: h.score, reverse=True)[:top_k]
