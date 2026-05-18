"""main.py —— demo only：同一组对话喂给四种 memory，看哪种还记得早期事实。"""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from chat import Chat, make_summarizer
from memory import Full, Memory, Summary, Tokens, Window, estimate_tokens

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=60.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]

SYSTEM = "你是友好的助手，用一句话简短回答。"

# 前 3 轮"灌入"事实，后 3 轮"回忆"事实 —— 看哪种 memory 还记得
DIALOG = [
    "你好，我叫张三",
    "我今年 25 岁",
    "我喜欢编程",
    "我刚才说我叫什么？",
    "我多大？",
    "我有什么爱好？",
]


def run(label: str, mem: Memory) -> None:
    print(f"\n=== {label} ===")
    chat = Chat(_client, _model, mem)
    for q in DIALOG:
        ans = chat.ask(q)
        toks = sum(estimate_tokens(m["content"]) for m in mem.messages())
        print(f"  Q: {q}")
        print(f"  A: {ans.strip()}  [ctx≈{toks}t, {len(mem.messages())}msg]")


def main() -> None:
    run("Full（全留）", Full(SYSTEM))
    run("Window(k=4)（只留最近 4 条）", Window(SYSTEM, k=4))
    run("Tokens(max=200)（token 预算）", Tokens(SYSTEM, max_tokens=200))
    run("Summary(k=4)（攒 4 条总结一次）",
        Summary(SYSTEM, summarize_fn=make_summarizer(_client, _model), k=4))


if __name__ == "__main__":
    main()
