"""
Prompt 前缀缓存（服务端 KV-Cache 复用）

这是和前两种缓存完全不同的层次的缓存：
  - exact_cache / semantic_cache：在【应用层】缓存"完整 prompt → 完整回答"
  - prefix_cache：在【模型推理层】缓存"prompt 前缀的注意力计算结果（KV cache）"

为什么前缀缓存值钱？
  LLM 推理分两步：
    1. Prefill：把 prompt 一次性"读进去"，建立 KV cache，O(N²)
    2. Decode：逐 token 生成回答
  Prefill 是大部分延迟的来源（尤其是长 system prompt + 长上下文）。
  如果两次请求的 prompt 前缀相同（比如 system prompt 一样），
  服务端可以直接复用上次的 KV cache，跳过 prefill！
  → 首字延迟从秒级降到毫秒级，成本降到 10-25%

谁支持？
  - Anthropic Claude API（需要在请求里显式标注 cache_control）
  - DeepSeek API（自动）
  - OpenAI 部分模型（自动，"cached input"）
  - 主流推理引擎（vLLM、SGLang）默认开启

本文件做什么？
  你用的是本地 MLX，不一定开启了前缀缓存。本脚本：
  1. 解释原理 + 用图示展示什么算"前缀复用"
  2. 在你的本地服务上做一个 A/B 测试：
     - 长 system prompt + 不同 user 问题 × N 次
     - 测首字延迟，看是否随次数下降（下降 = 服务端开了前缀缓存）
  3. 给出 Anthropic API 显式启用前缀缓存的代码片段（参考）
"""

import os
import time
import statistics
import requests
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


# ---------- 解释原理 ----------

def show_concept():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("什么是前缀缓存？")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    print("一次 LLM 调用的成本结构（极简版）：")
    print()
    print("  [Prefill 阶段]                 [Decode 阶段]")
    print("  读完整个 prompt        →       逐 token 生成回答")
    print("  O(N²) 延迟，最贵                每个 token O(N) 延迟")
    print()
    print(f"{Fore.YELLOW}前缀缓存做的事：把 Prefill 的中间结果（KV cache）存起来。{Style.RESET_ALL}")
    print()
    print("场景 A — 没有前缀缓存：")
    print("  请求 1: [长 system prompt][用户问题1]  → Prefill 全部 → Decode")
    print("  请求 2: [长 system prompt][用户问题2]  → Prefill 全部 → Decode")
    print("                                            ^^^^^^^^^ 重复算！")
    print()
    print("场景 B — 有前缀缓存：")
    print("  请求 1: [长 system prompt][用户问题1]  → Prefill 全部 → 缓存前缀")
    print("  请求 2: [长 system prompt][用户问题2]  → 复用前缀 + 仅算后缀")
    print(f"                                            {Fore.GREEN}快 5~50 倍{Style.RESET_ALL}")
    print()


# ---------- 测一下你的本地服务是否启用了前缀缓存 ----------

LONG_SYSTEM_PROMPT = """你是一名资深 Python 工程师，回答必须遵守以下所有规则：
1. 用 PEP 8 风格的代码，所有变量使用 snake_case 命名。
2. 给出代码后必须附带至少一段示例调用。
3. 解释要简明扼要，每句不超过 30 字。
4. 不要使用 emoji。
5. 不要承诺"100% 不会出错"这类绝对化表述。
6. 涉及性能问题时引用大 O 复杂度。
7. 涉及并发时优先推荐 asyncio 而不是 threading。
8. 涉及类型时使用 Python 3.10+ 的语法（list[int] 而不是 List[int]）。
9. 凡是涉及外部 IO 的函数都要写 timeout。
10. 保持中立，不评论代码风格的好坏。
11. 涉及 SQL 时优先使用参数化查询。
12. 涉及加密时不要自己实现，调用成熟库。
13. 错误处理用 raise，不要用 print。
14. 不要回避问题、不要绕弯子。
15. 任何代码示例的行数不要超过 30 行。
"""  # 这个 system 大概 ~300+ tokens，足够看出前缀缓存的效果


def measure_first_token_latency(user_question: str, system: str = LONG_SYSTEM_PROMPT) -> float:
    """用 streaming 测首字延迟（time-to-first-token）"""
    started = time.time()
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_question},
            ],
            "temperature": 0.0,
            "max_tokens": 50,
            "stream": True,
        },
        stream=True,
        timeout=60,
    )
    for line in response.iter_lines():
        if not line:
            continue
        # 收到第一行 data: 即视为"出第一个 token"
        if line.startswith(b"data: ") and b"[DONE]" not in line:
            return time.time() - started
    return time.time() - started


def demo_detect_prefix_cache():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("实测：你的本地服务是否启用了前缀缓存？")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    print("方法：固定 system prompt（~300 tokens），变换 user 问题各跑 4 次")
    print("    如果服务端有前缀缓存，第 2~4 次的首字延迟会明显下降")
    print("    （第 1 次必然要 prefill，它本来就慢）\n")

    questions = [
        "用 Python 实现冒泡排序",
        "用 Python 实现链表反转",
        "用 Python 实现二分查找",
        "用 Python 实现 LRU 缓存",
    ]

    latencies: list[float] = []
    for i, q in enumerate(questions, 1):
        try:
            ttft = measure_first_token_latency(q)
        except Exception as e:
            print(f"  [{i}] 失败: {e}")
            return
        latencies.append(ttft)
        print(f"  [{i}] 首字延迟: {Fore.YELLOW}{ttft*1000:>6.0f} ms{Style.RESET_ALL}  "
              f"(问: {q})")

    if len(latencies) < 4:
        return

    first = latencies[0]
    rest_avg = statistics.mean(latencies[1:])
    speedup = first / rest_avg if rest_avg else 0

    print(f"\n  第 1 次: {first*1000:.0f} ms")
    print(f"  第 2~4 次平均: {rest_avg*1000:.0f} ms")
    print(f"  比值: {Fore.YELLOW}{speedup:.2f}x{Style.RESET_ALL}\n")

    # 健康检查：若全部延迟 < 50ms，说明测量不可靠
    if max(latencies) * 1000 < 50:
        print(f"  {Fore.YELLOW}⚠️  全部首字延迟 < 50ms，说明服务端在缓冲响应，"
              f"无法可靠测出 TTFT{Style.RESET_ALL}")
        print(f"  本地 MLX 服务通常先生成完再吐流，这种情况无法判断前缀缓存。")
        print(f"  要在 vLLM / SGLang / 真实 API（Anthropic 等）上才看得清楚。")
    elif speedup >= 1.8:
        print(f"  {Fore.GREEN}✓ 看起来启用了前缀缓存{Style.RESET_ALL}")
        print(f"    （后续请求显著比第一次快，说明 system prompt 的 KV 被复用了）")
    elif speedup >= 1.2:
        print(f"  {Fore.YELLOW}~ 可能有部分缓存效果，或测量噪声{Style.RESET_ALL}")
    else:
        print(f"  {Fore.RED}✗ 没看到明显的前缀缓存{Style.RESET_ALL}")
        print(f"    本地 MLX 默认可能没开启。要在 vLLM/SGLang 上才能用上这个功能。")

    print()


# ---------- 给一个真实的"显式启用前缀缓存"的代码（仅参考，不调用） ----------

def show_anthropic_prefix_cache_example():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("Anthropic API 显式前缀缓存（参考代码，不在本机运行）")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    code = '''import anthropic

client = anthropic.Anthropic()
LONG_DOC = open("manual.txt").read()  # 比如 50k tokens 的手册

# 第一次：prefill 全部，标记为"可缓存"
resp1 = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=300,
    system=[
        {
            "type": "text",
            "text": LONG_DOC,
            "cache_control": {"type": "ephemeral"},   # ← 关键
        }
    ],
    messages=[{"role": "user", "content": "总结第 3 章"}],
)
# 看 resp1.usage.cache_creation_input_tokens 看缓存了多少

# 5 分钟内的第二次：直接命中缓存，前缀只要付 10% 价格
resp2 = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=300,
    system=[{"type": "text", "text": LONG_DOC,
             "cache_control": {"type": "ephemeral"}}],
    messages=[{"role": "user", "content": "总结第 5 章"}],
)
# resp2.usage.cache_read_input_tokens > 0 即命中
'''
    for line in code.splitlines():
        print(f"  {line}")
    print()
    print(f"{Fore.YELLOW}成本对比（Anthropic 官方价格）：{Style.RESET_ALL}")
    print(f"  写缓存: 1.25x 正常输入价")
    print(f"  读缓存: 0.10x 正常输入价  ← 长 system prompt 重复使用时降本 90%")
    print(f"  TTL:    5 分钟（默认） 或 1 小时（付费）")


def show_when_useful():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("前缀缓存什么时候真省钱？")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    print(f"{Fore.GREEN}✓ 高 ROI 场景（前缀长 + 重复请求）：{Style.RESET_ALL}")
    print("  - RAG：把检索到的长文档放在 system prompt（同文档多问几个问题）")
    print("  - Agent：长 system prompt + 工具定义不变，每轮变 user 消息")
    print("  - 多轮对话：每轮都重发完整历史（前缀稳步增长）")
    print("  - 文档分析：同一文档分不同问题问")
    print()
    print(f"{Fore.RED}✗ 低 ROI 场景（前缀短 / 每次都不同）：{Style.RESET_ALL}")
    print("  - 一次性查询（system 简单，无前缀可言）")
    print("  - 用户输入即 prompt（前缀就是用户消息，每次都不一样）")
    print("  - prompt 拼接顺序不固定（'动态拼' 会破坏前缀）")
    print()
    print(f"{Fore.YELLOW}使用提示：{Style.RESET_ALL}")
    print("  1. 把'稳定不变的内容'放最前面（system → 工具定义 → RAG 上下文 → user）")
    print("  2. 即使内容相同，顺序不同也算 prefix miss")
    print("  3. 监控 cache_read_input_tokens 占比，命中率 < 30% 说明你拼接顺序有问题")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("Prompt 前缀缓存 — 服务端 KV cache 复用")
    print(f"{'='*60}{Style.RESET_ALL}")

    show_concept()
    demo_detect_prefix_cache()
    show_anthropic_prefix_cache_example()
    show_when_useful()

    print(f"\n{Fore.CYAN}{'='*60}")
    print("和应用层缓存的关系")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    print("  应用层缓存（exact / semantic）：完整 prompt 命中 → 0 次 LLM 调用")
    print("  前缀缓存（本文件）         ：仍调 LLM，但前缀部分省钱")
    print()
    print(f"  {Fore.GREEN}两种可以叠加：{Style.RESET_ALL}")
    print("    1. 先查 exact_cache → 命中直接返回")
    print("    2. miss → 调 LLM，让服务端前缀缓存自动生效")
    print("    3. 把回答存进 exact_cache（甚至 semantic_cache）下次直接命中")
    print()


if __name__ == "__main__":
    main()
