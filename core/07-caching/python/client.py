"""client.py —— 把缓存夹在 LLM 客户端外面。整文件 cp 进项目即可。

`Cached.ask()` 先查 cache，命中直接返回；未命中调 LLM，结果写回 cache。
hits/misses 计数留给观察"省了多少钱"。
"""
from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from cache import Cache


@dataclass
class Cached:
    client: OpenAI
    model: str
    cache: Cache
    hits: int = 0
    misses: int = 0

    def ask(self, prompt: str) -> str:
        v = self.cache.get(prompt)
        if v is not None:
            self.hits += 1
            return v
        self.misses += 1
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.0,  # 缓存场景温度必须 0，否则同 prompt 不同答案，缓存毫无意义
        )
        v = resp.choices[0].message.content or ""
        self.cache.set(prompt, v)
        return v
