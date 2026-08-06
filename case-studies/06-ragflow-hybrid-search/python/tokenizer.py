"""tokenizer.py —— 共享分词工具，BM25 和 MockEmbedder 都用它。"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"\w+")


def tokenize(text: str) -> list[str]:
    """词级别分词：小写 + 字母数字 token，丢弃单字符。"""
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1]
