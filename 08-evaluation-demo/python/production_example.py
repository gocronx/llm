"""
综合示例：A/B 测试两个 Prompt，决定该用哪个

场景：你有一个"客服意图分类"任务，想对比：
  Prompt A: 简单直接版
  Prompt B: 加了示例的 Few-shot 版

谁更好？凭直觉？不行。跑评测。

本示例展示了一个真实工作流：
  1. 准备一个小型测试集（10 条意图分类样本）
  2. 同一个模型 + 两个不同 Prompt 各跑一遍
  3. 对每条样本用 exact 指标判定
  4. 输出：
     - 各自通过率
     - A 对 B 错的样本（B 在哪里弱）
     - B 对 A 错的样本（A 在哪里弱）
     - 决策建议

可改造：把 prompt 换成你自己业务的 prompt，把数据换成你自己的样本。
"""

import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from colorama import Fore, Style, init


init(autoreset=True)
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


# ---------- 待对比的两个 Prompt ----------

PROMPT_A = """你是客服意图分类器。
把用户消息分类到下列意图之一，只输出意图名（不要解释）：
- order_status（查订单）
- refund（退款）
- shipping（物流）
- product_info（咨询商品）
- complaint（投诉）
- other（其他）

用户消息：{message}
意图："""


PROMPT_B = """你是客服意图分类器。
把用户消息分类到下列意图之一，只输出意图名（不要解释）：
- order_status（查订单）
- refund（退款）
- shipping（物流）
- product_info（咨询商品）
- complaint（投诉）
- other（其他）

示例：
- "我的订单到哪了" → shipping
- "我想取消订单退钱" → refund
- "订单 12345 现在啥状态" → order_status
- "这件衣服是纯棉的吗" → product_info
- "你们家产品太垃圾了" → complaint

用户消息：{message}
意图："""


# ---------- 测试集 ----------

TESTSET = [
    ("我下的单还没收到货，到哪了", "shipping"),
    ("帮我看看订单 88123 的状态", "order_status"),
    ("我想退货，钱什么时候能退回来", "refund"),
    ("这个鞋子有 42 码的吗", "product_info"),
    ("差评！包装都是破的！", "complaint"),
    ("快递几天能到", "shipping"),
    ("订单显示已发货但是查不到物流", "shipping"),
    ("我要投诉客服态度", "complaint"),
    ("这款手机支持 5G 吗", "product_info"),
    ("能开发票吗", "other"),
]


# ---------- 调用 ----------

def call_with_prompt(prompt_template: str, message: str) -> str:
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": prompt_template.format(message=message)}],
            "temperature": 0.0,
            "max_tokens": 400,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


# 评测策略：模型可能展开思考，但最终的"意图名"应出现在输出中。
# 用 contains 替代 exact，更贴近真实业务（关心"分对了"，不关心"格式严丝合缝"）。
INTENT_NAMES = {"order_status", "refund", "shipping", "product_info", "complaint", "other"}


def grade_intent(actual: str, expected: str) -> bool:
    """判定意图分类是否正确：
    - 若输出里只出现一个已知意图名 → 命中即对
    - 若出现多个 → 取"最后出现"的那个（模型最终结论）
    """
    actual_lower = actual.lower()
    last_pos = -1
    last_intent = None
    for name in INTENT_NAMES:
        idx = actual_lower.rfind(name)
        if idx > last_pos:
            last_pos = idx
            last_intent = name
    return last_intent == expected


def run_variant(name: str, prompt_template: str) -> dict:
    """跑一个 prompt 变体，返回每条样本的 actual/pass"""
    print(f"\n{Fore.CYAN}跑 Prompt {name}…{Style.RESET_ALL}")

    started = time.time()
    results = [None] * len(TESTSET)

    def run_one(idx: int, msg: str, expected: str):
        try:
            actual = call_with_prompt(prompt_template, msg)
        except Exception as e:
            actual = f"[ERROR] {e}"
        return idx, msg, expected, actual

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(run_one, i, msg, exp)
                   for i, (msg, exp) in enumerate(TESTSET)]
        for fut in as_completed(futures):
            idx, msg, exp, actual = fut.result()
            ok = grade_intent(actual, exp)
            results[idx] = {
                "message": msg,
                "expected": exp,
                "actual": actual,
                "pass": ok,
            }
            mark = f"{Fore.GREEN}✓" if ok else f"{Fore.RED}✗"
            print(f"  {mark}{Style.RESET_ALL} {msg[:30]:30s} → {actual:20s}  "
                  f"(期望 {exp})")

    elapsed = time.time() - started
    passed = sum(1 for r in results if r["pass"])
    return {
        "name": name,
        "results": results,
        "passed": passed,
        "total": len(TESTSET),
        "pass_rate": passed / len(TESTSET),
        "elapsed_s": elapsed,
    }


def compare_variants(a: dict, b: dict):
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("A/B 对比报告")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    print(f"  Prompt A: {a['passed']}/{a['total']} = "
          f"{Fore.YELLOW}{a['pass_rate']*100:.1f}%{Style.RESET_ALL}  "
          f"耗时 {a['elapsed_s']:.1f}s")
    print(f"  Prompt B: {b['passed']}/{b['total']} = "
          f"{Fore.YELLOW}{b['pass_rate']*100:.1f}%{Style.RESET_ALL}  "
          f"耗时 {b['elapsed_s']:.1f}s")

    delta = (b["pass_rate"] - a["pass_rate"]) * 100
    if delta > 0:
        color, mark = Fore.GREEN, "B 更好"
    elif delta < 0:
        color, mark = Fore.RED, "A 更好"
    else:
        color, mark = Fore.YELLOW, "持平"
    print(f"\n  差距: {color}{delta:+.1f}% ({mark}){Style.RESET_ALL}\n")

    # A 对 B 错的样本
    a_only_pass = [
        (a["results"][i], b["results"][i])
        for i in range(len(TESTSET))
        if a["results"][i]["pass"] and not b["results"][i]["pass"]
    ]
    if a_only_pass:
        print(f"{Fore.RED}B 在这些样本上更弱：{Style.RESET_ALL}")
        for ar, br in a_only_pass:
            print(f"  ✗ {ar['message']}")
            print(f"    期望: {ar['expected']}")
            print(f"    A 答: {ar['actual']}  ✓")
            print(f"    B 答: {br['actual']}  ✗")

    # B 对 A 错的样本
    b_only_pass = [
        (a["results"][i], b["results"][i])
        for i in range(len(TESTSET))
        if not a["results"][i]["pass"] and b["results"][i]["pass"]
    ]
    if b_only_pass:
        print(f"\n{Fore.GREEN}B 在这些样本上更强：{Style.RESET_ALL}")
        for ar, br in b_only_pass:
            print(f"  ✓ {ar['message']}")
            print(f"    期望: {ar['expected']}")
            print(f"    A 答: {ar['actual']}  ✗")
            print(f"    B 答: {br['actual']}  ✓")

    # 决策建议
    print(f"\n{Fore.CYAN}决策建议：{Style.RESET_ALL}")
    if abs(delta) < 5 and len(TESTSET) < 30:
        print(f"  {Fore.YELLOW}⚠️  样本数 {len(TESTSET)} 太少，"
              f"差距 {abs(delta):.1f}% 可能在噪声范围内。"
              f"{Style.RESET_ALL}")
        print(f"  建议：扩到 100+ 样本再判断；或多跑几次取平均。")
    elif delta > 5:
        print(f"  {Fore.GREEN}✓ B 显著更好，建议采用。{Style.RESET_ALL}")
        print(f"  注意：B 比 A 多 ~{len(PROMPT_B) - len(PROMPT_A)} 字符，"
              f"成本会略高，权衡是否值得。")
    elif delta < -5:
        print(f"  {Fore.RED}✗ B 显著更差，保留 A。{Style.RESET_ALL}")
    else:
        print(f"  持平 → 选更便宜/更短的（即 Prompt A）。")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("综合示例：用评测决定该用哪个 Prompt")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    print(f"任务: 客服意图分类（6 个意图）")
    print(f"模型: {MODEL_ID}")
    print(f"测试集: {len(TESTSET)} 条")
    print(f"\n对比:")
    print(f"  Prompt A — 简单版（仅意图列表）")
    print(f"  Prompt B — Few-shot 版（带 5 个示例）\n")

    a = run_variant("A (简单版)", PROMPT_A)
    b = run_variant("B (Few-shot)", PROMPT_B)

    compare_variants(a, b)

    print(f"\n{Fore.CYAN}{'='*60}")
    print("这就是评测的真实价值")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    print("  没评测前：'Few-shot 应该更好吧？'  → 直觉，可能错")
    print("  评测后：用数据说话，看到 B 在哪里赢、在哪里输\n")
    print(f"{Fore.GREEN}下一步建议：{Style.RESET_ALL}")
    print("  1. 扩大测试集到 100+（小样本结论不可靠）")
    print("  2. 把这个流程接入 CI（每次改 prompt 自动跑）")
    print("  3. 用 regression_test.py 把'当前最好版本'存为 baseline\n")


if __name__ == "__main__":
    main()
