"""main.py —— demo only：四个多步任务，看 Agent 怎么规划工具序列。"""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from agent import Agent, Step

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=60.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


TASKS = [
    "北京今天天气怎么样？",
    "帮我计算 1999 * 3，然后搜索价格在这个范围内的产品",
    "对比北京和上海的天气，告诉我哪个城市更适合户外活动",
    "搜索所有手机产品，计算它们的平均价格",
]


def trace(s: Step) -> None:
    print(f"  [tool] {s.tool}({s.args}) -> {s.result[:80]}")


def main() -> None:
    for task in TASKS:
        print(f"\n>>> {task}")
        agent = Agent(_client, _model, on_step=trace)
        answer = agent.run(task)
        print(f"  [answer] {answer}")
        print(f"  ({len(agent.steps)} 次工具调用)")


if __name__ == "__main__":
    main()
