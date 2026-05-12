"""
LLM 裁判（LLM-as-Judge）

适合"没有标准答案、需要主观判断"的任务：
  - 文章质量评估
  - 客服回答是否专业
  - Agent 输出是否合理
  - 翻译/摘要的流畅度

本文件展示三种典型用法：
  1. 二元裁判（pass / fail + 理由）
  2. 评分裁判（1~5 分 + 理由）
  3. 成对比较（A 和 B 哪个更好，避免分数漂移）

并给出 LLM 裁判的"诚实警告"：何时不该用、有哪些坑。
"""

import os
import re
import json
import requests
from typing import Literal
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
JUDGE_MODEL_ID = os.getenv("JUDGE_MODEL_ID") or os.getenv("MODEL_ID")


JUDGE_SYSTEM = (
    "你是评测员。无论问题多复杂，你只输出一个 JSON 对象，"
    "不写任何分析过程、不写'让我想想'、不写解释。"
    "整个回复必须以 { 开头、以 } 结尾。"
)


def _call_judge(prompt: str) -> str:
    """裁判调用 —— temperature=0，加 system 约束，提高输出 JSON 的概率"""
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": JUDGE_MODEL_ID,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 600,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _parse_json(text: str) -> dict:
    """从 LLM 输出里提取 JSON，容错解析

    模型经常先写一堆思考再给 JSON。所以从右往左找最后一段
    成功解析的 {...}，并支持嵌套花括号。"""
    # 从右往左尝试每个 } 作为结尾
    for end in range(len(text) - 1, -1, -1):
        if text[end] != "}":
            continue
        # 从右侧 } 往左配对，找到平衡的 {
        depth = 0
        for start in range(end, -1, -1):
            if text[start] == "}":
                depth += 1
            elif text[start] == "{":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:end + 1])
                    except json.JSONDecodeError:
                        break
        if depth != 0:
            continue
    return {}


# ---------- 1. 二元裁判 ----------

BINARY_PROMPT = """你是严格的评测员。请判断回答是否符合标准。

【问题】
{question}

【评分标准】
{rubric}

【待评回答】
{answer}

请只输出一个 JSON：{{"pass": true|false, "reason": "<不超过 30 字的理由>"}}
不要输出任何其他内容。"""


def judge_binary(question: str, answer: str, rubric: str) -> tuple[bool, str]:
    """二元裁判：通过 / 不通过"""
    raw = _call_judge(BINARY_PROMPT.format(
        question=question, rubric=rubric, answer=answer))
    result = _parse_json(raw)
    return bool(result.get("pass", False)), str(result.get("reason", raw[:60]))


# ---------- 2. 评分裁判 ----------

SCORE_PROMPT = """你是严格的评测员。请按以下维度给回答打分（1~5 分整数）。

【问题】
{question}

【评分维度】
- accuracy: 事实是否正确
- completeness: 是否完整覆盖问题要求
- clarity: 表达是否清晰

【待评回答】
{answer}

请只输出一个 JSON：
{{"accuracy": <1-5>, "completeness": <1-5>, "clarity": <1-5>, "reason": "<一句话总评>"}}
不要输出任何其他内容。"""


def judge_score(question: str, answer: str) -> dict:
    """评分裁判：返回多维度分数"""
    raw = _call_judge(SCORE_PROMPT.format(question=question, answer=answer))
    result = _parse_json(raw)
    # 兜底：缺字段时给 0
    for key in ("accuracy", "completeness", "clarity"):
        result.setdefault(key, 0)
    result.setdefault("reason", raw[:60])
    return result


# ---------- 3. 成对比较 ----------

PAIRWISE_PROMPT = """你是严格的评测员。给定同一个问题的两个回答 A 和 B，判断哪个更好。

【问题】
{question}

【回答 A】
{answer_a}

【回答 B】
{answer_b}

请只输出一个 JSON：{{"winner": "A"|"B"|"tie", "reason": "<一句话理由>"}}
不要输出任何其他内容。"""


def judge_pairwise(
    question: str, answer_a: str, answer_b: str
) -> tuple[Literal["A", "B", "tie"], str]:
    """成对比较：返回胜者
    成对比较通常比绝对评分更稳定（人类评测也是这样）"""
    raw = _call_judge(PAIRWISE_PROMPT.format(
        question=question, answer_a=answer_a, answer_b=answer_b))
    result = _parse_json(raw)
    winner = result.get("winner", "tie")
    if winner not in ("A", "B", "tie"):
        winner = "tie"
    return winner, str(result.get("reason", ""))


def judge_pairwise_balanced(
    question: str, answer_a: str, answer_b: str
) -> tuple[Literal["A", "B", "tie"], str]:
    """位置去偏：交换顺序再问一次，两次结论一致才算数

    LLM 裁判存在'位置偏好'（更倾向选第一个或最后一个），
    交换两次取交集是最简单的去偏方法。"""
    w1, r1 = judge_pairwise(question, answer_a, answer_b)
    w2, r2 = judge_pairwise(question, answer_b, answer_a)
    # 第二次的 A 实际是原始 B
    w2_normalized = {"A": "B", "B": "A", "tie": "tie"}[w2]
    if w1 == w2_normalized:
        return w1, f"两次一致：{r1}"
    return "tie", f"两次冲突 → 视为平局（{r1} / {r2}）"


# ---------- Demo ----------

def demo_binary():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("用法 1：二元裁判（pass / fail）")
    print(f"{'='*60}{Style.RESET_ALL}")

    cases = [
        ("解释什么是闭包",
         "闭包就是函数能记住它定义时所在作用域里的变量，即使外层函数已经返回。",
         "答案需正确解释闭包概念，至少提及'函数'和'作用域/变量捕获'。"),
        ("解释什么是闭包",
         "闭包是一种网络安全协议。",
         "答案需正确解释闭包概念，至少提及'函数'和'作用域/变量捕获'。"),
    ]

    for q, a, rubric in cases:
        ok, reason = judge_binary(q, a, rubric)
        mark = f"{Fore.GREEN}✓ 通过" if ok else f"{Fore.RED}✗ 不通过"
        print(f"\n  {mark}{Style.RESET_ALL}")
        print(f"    回答: {a}")
        print(f"    裁判: {reason}")


def demo_score():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("用法 2：评分裁判（1~5 分）")
    print(f"{'='*60}{Style.RESET_ALL}")

    q = "用三句话介绍 Docker 的核心价值。"
    answers = [
        "Docker 是容器化技术，可以打包应用与其依赖一起分发。它解决了'在我机器上能跑'的问题。它让部署更快更可靠。",
        "Docker 很好用。",
    ]

    for a in answers:
        scores = judge_score(q, a)
        total = scores["accuracy"] + scores["completeness"] + scores["clarity"]
        print(f"\n  回答: {a[:60]}{'...' if len(a) > 60 else ''}")
        print(f"    accuracy={scores['accuracy']}  "
              f"completeness={scores['completeness']}  "
              f"clarity={scores['clarity']}  "
              f"{Fore.YELLOW}总分={total}/15{Style.RESET_ALL}")
        print(f"    总评: {scores['reason']}")


def demo_pairwise():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("用法 3：成对比较（位置去偏）")
    print(f"{'='*60}{Style.RESET_ALL}")

    q = "用一句话解释什么是数据库索引。"
    a = "索引是数据库中加速查询的数据结构，类似书的目录。"
    b = "索引就是个东西。"

    winner, reason = judge_pairwise_balanced(q, a, b)
    print(f"\n  问题: {q}")
    print(f"  A: {a}")
    print(f"  B: {b}")
    color = Fore.GREEN if winner == "A" else (Fore.YELLOW if winner == "tie" else Fore.RED)
    print(f"  {color}结论: {winner}{Style.RESET_ALL} — {reason}")


def demo_warnings():
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("LLM 裁判的诚实警告")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    print(f"{Fore.RED}1. 不稳定{Style.RESET_ALL}")
    print("   即使 temperature=0，同一题多次跑也可能给不同结论。")
    print("   建议：每个样本判 3 次取多数，或换成成对比较。\n")

    print(f"{Fore.RED}2. 位置偏好{Style.RESET_ALL}")
    print("   裁判倾向选第一个或最后一个回答。")
    print("   建议：用 judge_pairwise_balanced（交换顺序再问一次）。\n")

    print(f"{Fore.RED}3. 偏爱啰嗦{Style.RESET_ALL}")
    print("   裁判经常觉得长答案 = 好答案。")
    print("   建议：评分维度里加'是否简洁'，或控制答案长度。\n")

    print(f"{Fore.RED}4. 同模型偏见{Style.RESET_ALL}")
    print("   用 GPT-4 评 GPT-4 的输出，分数会偏高。")
    print("   建议：用更强的模型当裁判，或换不同厂商。\n")

    print(f"{Fore.RED}5. 慢且贵{Style.RESET_ALL}")
    print("   每个样本多一次 LLM 调用。1000 个样本 = 1000 次额外调用。")
    print("   建议：先用规则指标筛掉一批，剩下的再让 LLM 判。\n")

    print(f"{Fore.GREEN}什么时候才该用 LLM 裁判？{Style.RESET_ALL}")
    print("   ✅ 真的没有标准答案（如：写一首诗、写客服话术）")
    print("   ✅ 规则指标已经覆盖不了（如：判断是否'通顺'）")
    print("   ❌ 不要因为'偷懒不想想清楚标准'就用 LLM 裁判\n")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("LLM-as-Judge：让 LLM 当评测员")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    demo_binary()
    demo_score()
    demo_pairwise()
    demo_warnings()


if __name__ == "__main__":
    main()
