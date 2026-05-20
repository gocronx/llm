"""main.py —— demo only：三 agent 协作写一篇博客（writer → reviewer → editor）。"""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from agent import Agent
from orchestrator import Step, run_parallel, run_sequential

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=60.0)
_openai = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


def build_team() -> dict[str, Agent]:
    """三个角色：写、审、改。每个 role 决定行为，task 决定具体输出。"""
    return {
        "writer": Agent("writer",
            "你是技术博客写手。给出 200 字内的文章主体，不要标题。",
            _openai, _model),
        "reviewer": Agent("reviewer",
            "你是技术评审员。读上游产物，按 - 列表给 3 条具体改进建议，每条不超过 20 字。",
            _openai, _model),
        "editor": Agent("editor",
            "你是编辑。综合 writer 的初稿和 reviewer 的建议，输出最终成稿。"
            "禁止添加解释，直接输出修改后的文章。",
            _openai, _model),
    }


def scenario_sequential() -> None:
    print("\n=== 顺序工作流：writer → reviewer → editor ===")
    workflow = [
        Step("draft",  "writer",   "写一段关于 Python 异步编程的简短科普"),
        Step("review", "reviewer", "评审上面的初稿", depends_on=["draft"]),
        Step("final",  "editor",   "按 reviewer 建议修改 draft，输出终稿",
             depends_on=["draft", "review"]),
    ]
    results = run_sequential(build_team(), workflow)
    for sid in ("draft", "review", "final"):
        print(f"\n--- {sid} ---\n{results[sid]}")


def scenario_parallel() -> None:
    print("\n=== 并行工作流：3 个 writer 各写一段 ===")
    team = build_team()
    # 都用 writer 角色，但 task 不同。并行没有依赖
    steps = [
        Step("py",   "writer", "写一句 Python 的优点"),
        Step("rust", "writer", "写一句 Rust 的优点"),
        Step("go",   "writer", "写一句 Go 的优点"),
    ]
    results = run_parallel(team, steps)
    for sid in ("py", "rust", "go"):
        print(f"  [{sid}] {results[sid].strip()}")


def main() -> None:
    scenario_sequential()
    scenario_parallel()


if __name__ == "__main__":
    main()
