"""test.py —— 只验证一件事：LLM 在三类问题上调对了工具。"""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from tools import schemas

load_dotenv()
# trust_env=False 见 main.py 的注释（绕系统代理）
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=httpx.Client(trust_env=False, timeout=60.0),
)
_model = os.environ["MODEL_ID"]

CASES = [
    ("北京天气怎么样？", "get_weather"),
    ("156 除以 12", "calculate"),
    ("搜索笔记本相关的产品", "search_products"),
]


def main() -> None:
    passed = 0
    for q, expected in CASES:
        resp = _client.chat.completions.create(
            model=_model, messages=[{"role": "user", "content": q}], tools=schemas()
        )
        tcs = resp.choices[0].message.tool_calls or []
        got = tcs[0].function.name if tcs else "(no tool call)"
        ok = got == expected
        passed += ok
        print(f"{'✓' if ok else '✗'} {q!r:40s} expected={expected:18s} got={got}")
    print(f"\n{passed}/{len(CASES)} passed")


if __name__ == "__main__":
    main()
