"""main.py —— demo only: 长对话场景下治理的实战效果.

跑这个 demo:
  1. context_window 故意设 2000 token (小到几乎一定超, 强制让 snip 触发)
  2. max_tool_result 故意设 1500 字符 (小, 容易被 budget 截)
  3. 多步任务塞 web_fetch (8KB 网页 -> 触发 microcompact + budget)

观察输出:
  - [tool] N 次工具调用
  - [govern] real=X → view=Y 会随着对话变长出现 (X > Y 时治理生效)
  - 最后给出最终答案

如果模型很聪明把多个工具合并到一次 assistant.tool_calls, 治理可能在前几轮不触发,
但跑到 3+ 轮 web_fetch 后必然超 2000 token 预算, snip 会出手."""

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


TASK = (
    "请帮我做这几件事:\n"
    "1. 抓取 https://example.com/article-A 的内容并总结\n"
    "2. 抓取 https://example.com/article-B 的内容并总结\n"
    "3. 抓取 https://example.com/article-C 的内容并总结\n"
    "4. 搜索价格 100-500 的产品\n"
    "5. 搜索价格 500-1000 的产品\n"
    "6. 最后告诉我北京天气和你看过的所有内容的一句话总结"
)


def trace_step(s: Step) -> None:
    print(f"  [tool] {s.tool}({list(s.args.keys())}) -> {len(s.result)} chars")


def trace_govern(before_n: int, after_n: int, before_tok: int, after_tok: int) -> None:
    if before_n != after_n or before_tok != after_tok:
        n_diff = (
            f"{before_n}->{after_n}msgs" if before_n != after_n else f"{before_n}msgs"
        )
        t_diff = (
            f"{before_tok}->{after_tok}tok"
            if before_tok != after_tok
            else f"{before_tok}tok"
        )
        print(f"  [govern] {n_diff}, {t_diff}")


def main() -> None:
    agent = Agent(
        _client,
        _model,
        max_iterations=20,
        context_window_tokens=2000,  # 故意调小, 强制 snip 触发
        max_tool_result_chars=1500,  # 故意调小, 强制 budget 截断生效
        on_step=trace_step,
        on_govern=trace_govern,
    )
    answer = agent.run(TASK)
    print(f"\n>>> 最终答案:\n{answer}")
    print(f"\n>>> 工具调用 {len(agent.steps)} 次, 真实历史 {len(agent.messages)} 条")


if __name__ == "__main__":
    main()
