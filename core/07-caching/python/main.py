"""main.py —— demo only：对比 Exact / Semantic 在"几乎相同问题"上的命中率。"""
from __future__ import annotations

import os
import time

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from cache import Exact, Semantic
from client import Cached

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=60.0)
_openai = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


# 5 个语义相近的问题：Exact 全 miss，Semantic 应该有几个 hit
QUESTIONS = [
    "什么是 Python？",
    "Python 是什么？",
    "请介绍下 Python 编程语言",
    "Python 这门语言主要用来做什么？",
    "什么是 Rust？",  # 这条应该 miss
]


def run(label: str, cached: Cached) -> None:
    print(f"\n=== {label} ===")
    for q in QUESTIONS:
        t0 = time.perf_counter()
        ans = cached.ask(q)
        ms = (time.perf_counter() - t0) * 1000
        print(f"  [{ms:6.1f}ms] {q}\n     -> {ans.strip()[:60]}")
    print(f"  hits={cached.hits} misses={cached.misses}")


def main() -> None:
    run("Exact（完全相同才命中）", Cached(_openai, _model, Exact()))
    run("Semantic(threshold=0.5)（前 4 句应该串起来）",
        Cached(_openai, _model, Semantic(threshold=0.5)))


if __name__ == "__main__":
    main()
