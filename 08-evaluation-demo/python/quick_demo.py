"""
快速入门：3 种最常用的评测方法

核心问题：你改了 Prompt / 换了模型，怎么知道效果是变好还是变差？
答：用评测。

本文件演示三种最基础的评测方式：
  1. 精确匹配：适合"答案唯一"的任务（数学、事实问答）
  2. 关键词匹配：适合"开放式但有要点"的任务
  3. LLM 裁判：适合"开放式 + 主观评价"的任务

跑一次就能直观感受到：什么场景该用哪种方法。
"""

import os
import requests
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


def call_llm(prompt: str, temperature: float = 0.0) -> str:
    """调用 LLM，返回纯文本"""
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": 200,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


# ---------- 三种评测方法 ----------

def metric_exact(actual: str, expected: str) -> bool:
    """精确匹配：去空格后字符串相等"""
    return actual.strip() == expected.strip()


def metric_keywords(actual: str, keyword_groups: list[str]) -> bool:
    """关键词匹配：每组关键词必须命中其中之一
    keyword_groups 例：["函数", "自身|自己"] 表示必须出现"函数"，且必须出现"自身"或"自己"
    """
    for group in keyword_groups:
        alternatives = group.split("|")
        if not any(alt in actual for alt in alternatives):
            return False
    return True


def metric_llm_judge(question: str, answer: str, rubric: str) -> tuple[bool, str]:
    """LLM 裁判：让另一个 LLM 评判答案

    实现复用 llm_judge.py，避免重复维护。"""
    from llm_judge import judge_binary
    return judge_binary(question, answer, rubric)


# ---------- 三个对比演示 ----------

def demo_exact_match():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("方法 1：精确匹配 — 适合答案唯一的任务")
    print(f"{'='*60}{Style.RESET_ALL}")

    cases = [
        ("1+1 等于多少？只回答数字。", "2"),
        ("12 乘以 12 等于多少？只回答数字。", "144"),
        ("HTTP 默认端口号是多少？只回答数字。", "80"),
    ]

    passed = 0
    for question, expected in cases:
        actual = call_llm(question)
        ok = metric_exact(actual, expected)
        passed += ok
        mark = f"{Fore.GREEN}✓" if ok else f"{Fore.RED}✗"
        print(f"\n  {mark}{Style.RESET_ALL} {question}")
        print(f"    期望: {expected}")
        print(f"    实际: {actual}")

    print(f"\n  通过率: {Fore.YELLOW}{passed}/{len(cases)}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}适用场景：{Style.RESET_ALL}有标准答案、答案唯一")
    print(f"  {Fore.YELLOW}陷阱：{Style.RESET_ALL}多一个标点、多一个换行就算失败")


def demo_keyword_match():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("方法 2：关键词匹配 — 适合开放但有要点的任务")
    print(f"{'='*60}{Style.RESET_ALL}")

    cases = [
        ("用一句话解释什么是递归。", ["函数", "自身|自己"]),
        ("请简要解释 HTTPS 比 HTTP 安全在哪里。",
         ["加密|TLS|SSL", "证书|身份|中间人"]),
    ]

    passed = 0
    for question, keywords in cases:
        actual = call_llm(question)
        ok = metric_keywords(actual, keywords)
        passed += ok
        mark = f"{Fore.GREEN}✓" if ok else f"{Fore.RED}✗"
        print(f"\n  {mark}{Style.RESET_ALL} {question}")
        print(f"    要求关键词: {keywords}")
        print(f"    回答: {actual[:80]}{'...' if len(actual) > 80 else ''}")

    print(f"\n  通过率: {Fore.YELLOW}{passed}/{len(cases)}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}适用场景：{Style.RESET_ALL}答案有多种表达，但应包含某些要点")
    print(f"  {Fore.YELLOW}陷阱：{Style.RESET_ALL}关键词命中不等于答得对（可能上下文是反义）")


def demo_llm_judge():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("方法 3：LLM 裁判 — 适合主观、开放式的任务")
    print(f"{'='*60}{Style.RESET_ALL}")

    cases = [
        {
            "question": "为什么程序员更喜欢用 Linux 做开发？",
            "rubric": "答案应该提到至少两点：开源/自由、命令行/工具链、性能、与服务器一致 中的任意两点。语言通顺、没有事实性错误。",
        },
        {
            "question": "用通俗的话解释什么是 Docker。",
            "rubric": "应包含'隔离'或'打包'相关概念，至少给出一个类比（例如集装箱、虚拟机对比），通俗易懂。",
        },
    ]

    passed = 0
    for case in cases:
        actual = call_llm(case["question"])
        ok, reason = metric_llm_judge(case["question"], actual, case["rubric"])
        passed += ok
        mark = f"{Fore.GREEN}✓" if ok else f"{Fore.RED}✗"
        print(f"\n  {mark}{Style.RESET_ALL} {case['question']}")
        print(f"    回答: {actual[:80]}{'...' if len(actual) > 80 else ''}")
        print(f"    裁判: {reason}")

    print(f"\n  通过率: {Fore.YELLOW}{passed}/{len(cases)}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}适用场景：{Style.RESET_ALL}没有标准答案、需要综合判断")
    print(f"  {Fore.YELLOW}陷阱：{Style.RESET_ALL}慢且贵（每个样本多一次 LLM 调用）；裁判本身也会出错")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("评测快速入门：三种最常用的方法")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    print(f"{Fore.YELLOW}核心理念：{Style.RESET_ALL}")
    print("  改了 Prompt / 换了模型 / 升级了版本，凭直觉判断好坏 = 自欺欺人")
    print("  评测的目标不是'追求高分'，而是'快速发现退化'\n")

    demo_exact_match()
    demo_keyword_match()
    demo_llm_judge()

    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("怎么选？")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    print(f"  {Fore.GREEN}能用精确匹配就别用关键词{Style.RESET_ALL}（快、稳、零成本）")
    print(f"  {Fore.GREEN}能用关键词就别用 LLM 裁判{Style.RESET_ALL}（裁判慢、贵、且不稳定）")
    print(f"  {Fore.YELLOW}LLM 裁判是最后手段{Style.RESET_ALL}：用于真正主观的任务\n")

    print("下一步：")
    print("  python basic_metrics.py     # 看更多指标（regex、JSON 等价、Rouge-L）")
    print("  python dataset_eval.py      # 用一个测试集跑批量评测")
    print("  python regression_test.py   # 把当前结果存为 baseline，下次升级时对比\n")


if __name__ == "__main__":
    main()
