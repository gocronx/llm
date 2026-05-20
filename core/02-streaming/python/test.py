"""test.py —— 简单冒烟测试：
1) 纯文本流式至少要 yield 出若干个 chunk（不能是一坨大块）。
2) 流式 + tool 场景里 get_weather 被调到，且最终文本里包含 25 或 "晴"。"""
from __future__ import annotations

import os

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


def test_text_stream() -> bool:
    chunks = list(stream_text(_client, _model, "回答 OK 两个字。"))
    ok = len(chunks) >= 1 and "".join(chunks).strip() != ""
    print(f"{'✓' if ok else '✗'} text stream: {len(chunks)} chunks")
    return ok


def test_stream_with_tools() -> bool:
    tool_called = False
    final_text = ""
    for ev in stream_with_tools(_client, _model, "北京今天天气怎么样？"):
        if ev["type"] == "tool_call" and ev["name"] == "get_weather":
            tool_called = True
        elif ev["type"] == "text":
            final_text += ev["delta"]
    ok = tool_called and ("15" in final_text or "晴" in final_text)
    print(f"{'✓' if ok else '✗'} stream+tools: tool_called={tool_called} text={final_text[:40]!r}")
    return ok


def main() -> None:
    passed = sum([test_text_stream(), test_stream_with_tools()])
    print(f"\n{passed}/2 passed")


if __name__ == "__main__":
    main()
