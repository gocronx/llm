"""main.py —— demo only：三种路由策略在同一个问题上的对比。"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from loader import load_skills_cached
from router import compose, route_keyword, route_llm, run_implicit

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=120.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]
_skills = load_skills_cached(Path(__file__).parent / "skills")


PROMPTS = [
    "把这句翻译成英文：今天天气真好",
    "写一个 SQL：查出过去 7 天每天的订单数",
    "下面这段代码有安全问题吗？\nuser_input = request.args.get('q')\nquery = f\"SELECT * FROM users WHERE name = '{user_input}'\"",
    "我家狗丢了，怎么办？",  # 应该无 skill 匹配
]


def show(label: str, loaded: list, answer: str | None = None) -> None:
    names = [s.name if hasattr(s, "name") else s for s in loaded]
    print(f"  [{label}] loaded: {names}")
    if answer:
        print(f"           answer: {answer[:120]}")


def main() -> None:
    print(f"加载到 {len(_skills)} 个 skill：{[s.name for s in _skills]}\n")
    for q in PROMPTS:
        print(f">>> {q}")
        kw = route_keyword(q, _skills)
        show("keyword", kw)

        llm = route_llm(_client, _model, q, _skills)
        show("llm    ", llm)

        ans, impl = run_implicit(_client, _model, q, _skills)
        show("implicit", impl, ans)
        print()


if __name__ == "__main__":
    main()
