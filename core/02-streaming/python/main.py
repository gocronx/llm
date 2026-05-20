"""main.py —— demo only：两个场景。
1) 纯文本流式：对比首字延迟。
2) 流式 + function call：tool_calls 的 delta 累积。"""
from __future__ import annotations

import os
import time

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from client import stream_text, stream_with_tools

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=60.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


def scenario_text_stream() -> None:
    print(">>> 纯文本流式：写一段 50 字内的 AI 简介")
    t0 = time.perf_counter()
    first_token_at: float | None = None
    n = 0
    for delta in stream_text(_client, _model, "用 50 字内介绍人工智能。"):
        if first_token_at is None:
            first_token_at = time.perf_counter() - t0
        print(delta, end="", flush=True)
        n += 1
    total = time.perf_counter() - t0
    print(f"\n[首字 {first_token_at:.2f}s / 总 {total:.2f}s / {n} chunks]\n")


def scenario_stream_with_tools() -> None:
    print(">>> 流式 + function call：北京天气")
    for event in stream_with_tools(_client, _model, "北京今天天气怎么样？"):
        if event["type"] == "tool_call":
            print(f"[tool] {event['name']}({event['args']}) -> {event['result']}")
        else:
            print(event["delta"], end="", flush=True)
    print()


def main() -> None:
    scenario_text_stream()
    scenario_stream_with_tools()


if __name__ == "__main__":
    main()
