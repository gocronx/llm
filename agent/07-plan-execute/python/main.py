"""main.py —— demo only：几个多步任务，看 Agent 先出计划、逐步执行、必要时改计划。"""

from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from agent import PlanExecuteAgent

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=60.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


TASKS = [
    "对比北京和上海的天气，告诉我哪个更适合户外活动",
    "搜索所有手机产品，算出它们的平均价格",
    "查一下深圳天气，如果下雨就推荐适合室内用的产品",
]


def trace(kind: str, detail: str) -> None:
    print(f"  [{kind}] {detail}")


def main() -> None:
    for task in TASKS:
        print(f"\n>>> {task}")
        agent = PlanExecuteAgent(_client, _model, on_event=trace)
        answer = agent.run(task)
        print(f"  [answer] {answer}")
        print(f"  ({len(agent.transcript)} 步执行完成)")


if __name__ == "__main__":
    main()
