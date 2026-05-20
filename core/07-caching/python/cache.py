"""cache.py —— 两种 LLM 应用层缓存。整文件 cp 进项目即可。

Exact     —— SHA256(prompt) 当 key，命中要求 prompt 完全一致。最稳，命中率最低。
Semantic  —— 把 prompt 拆成字符 2-gram，按 Jaccard 相似度找近邻；阈值控制"省钱 vs 答错"。

接口同样是 get(prompt) / set(prompt, value)。Cached() wrapper 用同一套接口换缓存策略。

注：这是应用层缓存（prompt → answer 整对存）。还有服务端 KV-cache 复用
（"前缀缓存"）那是另一回事，模型推理引擎做的，见 README。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol


class Cache(Protocol):
    def get(self, prompt: str) -> str | None: ...
    def set(self, prompt: str, value: str) -> None: ...


# ---- Exact ----

class Exact:
    """SHA256 精确匹配。可选磁盘持久化。"""
    def __init__(self, path: str | None = None):
        self._mem: dict[str, str] = {}
        self._path = Path(path) if path else None
        if self._path and self._path.exists():
            self._mem = json.loads(self._path.read_text(encoding="utf-8"))

    def _key(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def get(self, prompt: str) -> str | None:
        return self._mem.get(self._key(prompt))

    def set(self, prompt: str, value: str) -> None:
        self._mem[self._key(prompt)] = value
        if self._path:
            self._path.write_text(json.dumps(self._mem, ensure_ascii=False), encoding="utf-8")


# ---- Semantic ----

def _bigrams(s: str) -> set[str]:
    s = s.strip().lower()
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else {s}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


class Semantic:
    """字符 2-gram Jaccard 相似度。阈值默认 0.7：
    - 太低（<0.5）会把不同问题的答案串错；
    - 太高（>0.9）命中率不如 Exact。
    生产里换 sentence-transformers + cosine。
    """
    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
        self._entries: list[tuple[set[str], str, str]] = []  # (bigrams, raw_prompt, value)

    def get(self, prompt: str) -> str | None:
        bg = _bigrams(prompt)
        best_score = 0.0
        best_value: str | None = None
        for stored_bg, _, value in self._entries:
            s = _jaccard(bg, stored_bg)
            if s > best_score:
                best_score, best_value = s, value
        return best_value if best_score >= self.threshold else None

    def set(self, prompt: str, value: str) -> None:
        self._entries.append((_bigrams(prompt), prompt, value))
