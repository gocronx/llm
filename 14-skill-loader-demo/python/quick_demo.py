"""Compare 3 skill-loading modes on the same prompts: none, all, auto-routed."""

import argparse
import sys
import time

from skill_loader import (
    BASE_SYSTEM, Composed, call_llm, compose, load_skills, route_keyword,
    route_llm, run_implicit, system_token_estimate,
)

# 测试 query 分四组，故意暴露两种路由的差异
QUERIES = [
    # A. 简单 / trigger 字面命中（基线，两个路由都该 hit）
    "我们刚开完一次会，原始记录：'王经理：下周一前发布新功能；张工：会前测压'。整理成行动项。",
    "审查这段 Python：subprocess.run(f'curl {user_input}', shell=True)",
    "写一个 PostgreSQL 查询：找出过去 7 天下单超过 3 次的用户邮箱。",
    "翻译成英文：能否帮忙看一下这个错误日志，紧急。",

    # B. 同义词改写（trigger 都不在，keyword 应该 miss、LLM 应该 hit）
    "把这段对话录音变成结构化文档",                      # → meeting-notes-formatter
    "把这段中文改成英语：你好世界",                       # → translation-zh-en（没"翻译"）
    "我的 schema 怎么改才能加索引？",                    # → sql-query-builder（没"SQL/查询"）

    # C. 陷阱（keyword 容易选错或 over-match）
    "如何防止 sql injection",                          # → code-review-security（不是 sql-query-builder!）
    "客户骂我们家产品垃圾，怎么回复",                     # → customer-support-reply（没"客服/投诉"）

    # D. 负样本（任何 skill 都不该 fire）
    "今天天气怎么样？",
    "1+1 等于几",
]


def run_mode(mode: str, queries: list[str], skills, top_k: int = 2):
    print(f"\n=== mode: {mode} ===")
    for i, q in enumerate(queries, 1):
        started = time.time()
        if mode == "auto-implicit":
            answer, loaded_names = run_implicit(q, skills)
            loaded = loaded_names or ["(none)"]
            sys_tokens = system_token_estimate("\n".join(
                f"  - {s.name}: {s.description}" for s in skills
            ))
        else:
            composed = compose(q, skills, mode=mode, top_k=top_k)
            answer = call_llm(composed.system, q)
            loaded = composed.loaded_skill_names or ["(none)"]
            sys_tokens = system_token_estimate(composed.system)
        elapsed = int((time.time() - started) * 1000)
        print(f"\n[{i}] {q}")
        print(f"    loaded: {loaded}  sys_tokens≈{sys_tokens}  {elapsed}ms")
        print(f"    answer: {answer[:180]}{'...' if len(answer) > 180 else ''}")


def show_routing_only(skills):
    """Don't call LLM, just show which skills each strategy picks."""
    print("=== routing only (no LLM call for generation) ===")
    print(f"{'query':<50}  {'keyword':<30}  {'llm-router':<30}")
    for q in QUERIES:
        kw = [s.name for s in route_keyword(q, skills)]
        try:
            llm = [s.name for s in route_llm(q, skills)]
        except Exception as e:
            llm = [f"[err: {e}]"]
        print(f"{q[:48]:<50}  {','.join(kw) or '-':<30}  {','.join(llm) or '-':<30}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["none", "all", "auto-keyword", "auto-llm", "auto-implicit",
                 "compare", "route-only"],
        default="compare",
        help="compare: run none/all/auto-keyword/auto-implicit. route-only: just print routing picks.",
    )
    args = parser.parse_args()

    skills = load_skills()
    print(f"loaded {len(skills)} skills from skills/")

    if args.mode == "route-only":
        show_routing_only(skills)
        return

    if args.mode == "compare":
        for m in ("none", "all", "auto-keyword", "auto-implicit"):
            run_mode(m, QUERIES, skills)
    else:
        run_mode(args.mode, QUERIES, skills)


if __name__ == "__main__":
    main()
