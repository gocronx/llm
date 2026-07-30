"""运行 LangGraph 多步任务恢复案例。

默认用 mock AI，保证开箱即跑；传 --real-llm 使用 .env 中的模型。
"""
from __future__ import annotations

import argparse

from dotenv import load_dotenv
from graph import build_graph, initial_state
from planner import OpenAIRecoveryPlanner, RuleBasedRecoveryPlanner
from tools import ToolSandbox


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--real-llm",
        action="store_true",
        help="使用 .env 中配置的 OpenAI 兼容 API",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv("../.env")
    args = parse_args()
    planner = (
        OpenAIRecoveryPlanner()
        if args.real_llm
        else RuleBasedRecoveryPlanner()
    )
    sandbox = ToolSandbox()
    graph = build_graph(sandbox, planner)
    result = graph.invoke(
        initial_state(),
        config={
            "recursion_limit": 50,
            "configurable": {"thread_id": "demo-run-1"},
        },
    )

    print("\nLangGraph execution trace")
    print("=" * 60)
    for event in result["events"]:
        print(f"• {event}")
    print("=" * 60)
    print(f"status: {result['status']}")
    print(f"committed_steps: {result['committed_steps']}")
    print(f"sent_emails: {sandbox.sent_emails}")


if __name__ == "__main__":
    main()
