"""
生产级分层缓存策略

把前面三种缓存按"风险递增、成本递减"的顺序串起来：

    用户 prompt
        │
        ▼
   ┌─────────┐    HIT    返回缓存（毫秒级，零成本）
   │ 精确缓存 │─────────► 0% 错答风险
   └─────────┘
        │ MISS
        ▼
   ┌─────────┐    HIT    返回缓存（毫秒级，零成本）
   │ 语义缓存 │─────────► 1-5% 错答风险（看阈值）
   └─────────┘
        │ MISS
        ▼
   ┌─────────────────┐
   │ 调真实 LLM API   │  服务端会自动用前缀缓存（如果支持）
   └─────────────────┘
        │
        ▼
   把回答写回精确缓存（永远写）+ 写回语义缓存（可选）

为什么不全用语义缓存？
  - 精确命中 = 0% 错答；语义命中 = 有错答风险
  - 同样能省，肯定优先选风险低的
  - 精确层兜底语义层的"真重复"场景

本文件输出：分层 vs 单层的成本/质量对比报告。
"""

import os
import time
import requests
from dataclasses import dataclass, field
from dotenv import load_dotenv
from colorama import Fore, Style, init

from exact_cache import ExactCache, call_llm
from semantic_cache import SemanticCache

init(autoreset=True)
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


# ---------- 分层缓存 ----------

@dataclass
class LayeredStats:
    exact_hits: int = 0
    semantic_hits: int = 0
    misses: int = 0
    total_latency_ms: int = 0
    total_tokens: int = 0  # 真实 API 调用消耗的（前两层都是 0）

    @property
    def total(self) -> int:
        return self.exact_hits + self.semantic_hits + self.misses


class LayeredCache:
    """精确 + 语义 两层缓存"""

    def __init__(self, semantic_threshold: float = 0.70, ttl: int = None):
        self.exact = ExactCache(ttl_seconds=ttl)
        self.semantic = SemanticCache(threshold=semantic_threshold)
        self.stats = LayeredStats()

    def get_or_compute(
        self, prompt: str, temperature: float = 0.0
    ) -> tuple[str, str]:
        """返回 (回答, 命中层级名)"""
        started = time.time()

        # 第一层：精确
        cached = self.exact.get(prompt, MODEL_ID, temperature)
        if cached is not None:
            self.stats.exact_hits += 1
            self.stats.total_latency_ms += int((time.time() - started) * 1000)
            return cached, "EXACT"

        # 第二层：语义
        sem_hit = self.semantic.get(prompt)
        if sem_hit is not None:
            response, original, score = sem_hit
            self.stats.semantic_hits += 1
            # 也写回精确缓存（下次精确命中）
            self.exact.put(prompt, MODEL_ID, temperature, response,
                           tokens=0, latency_ms=1)
            self.stats.total_latency_ms += int((time.time() - started) * 1000)
            return response, f"SEMANTIC(sim={score:.2f}, orig='{original}')"

        # 第三层：真实 API
        text, tokens, ms = call_llm(prompt, temperature)
        self.exact.put(prompt, MODEL_ID, temperature, text, tokens, ms)
        self.semantic.put(prompt, text, tokens, ms)
        self.stats.misses += 1
        self.stats.total_tokens += tokens
        self.stats.total_latency_ms += int((time.time() - started) * 1000)
        return text, "API"


# ---------- 真实负载 ----------

# 模拟客服 30 条请求：30% 完全重复、40% 同义改写、30% 全新
WORKLOAD = [
    # 第一波：4 个原始问题
    "怎么修改账号密码？",
    "如何申请退款？",
    "订单什么时候发货？",
    "可以开发票吗？",

    # 重复（精确层应该命中）
    "怎么修改账号密码？",
    "如何申请退款？",
    "订单什么时候发货？",

    # 同义改写（语义层有机会命中）
    "我想改密码该怎么操作",
    "退款怎么办理",
    "订单几天能到",
    "你们能开发票吗",

    # 又一波同义
    "怎么改下密码",
    "我要退款",
    "啥时候发货",

    # 全新问题
    "你们家最贵的产品是什么",
    "客服上班时间是几点",
    "可以加微信吗",
    "怎么联系人工",

    # 再次重复（验证缓存稳定性）
    "怎么修改账号密码？",
    "如何申请退款？",
    "可以开发票吗？",

    # 同义但带"否定/约束"的危险案例
    "怎么修改账号密码？",
    "怎么不修改账号密码",          # 危险：差一个字意思相反
    "如何申请退款？",
    "如何申请部分退款",            # 危险：多一个修饰词

    # 末尾混杂
    "客服上班时间是几点",
    "客服几点上班",
    "怎么联系人工",
    "今天几号了",
    "感谢你的帮助",
]


def run_strategy(name: str, fn) -> dict:
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"策略：{name}")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    started = time.time()
    api_calls = 0
    layer_log: dict[str, int] = {}

    for i, q in enumerate(WORKLOAD, 1):
        layer = fn(q)
        if layer == "API":
            api_calls += 1
        layer_log[layer.split("(")[0]] = layer_log.get(layer.split("(")[0], 0) + 1
        color = (
            Fore.GREEN if layer.startswith("EXACT") else
            Fore.YELLOW if layer.startswith("SEMANTIC") else
            Fore.RED
        )
        print(f"  [{i:2d}] {color}{layer:<30s}{Style.RESET_ALL}  {q}")

    elapsed_ms = int((time.time() - started) * 1000)
    return {
        "elapsed_ms": elapsed_ms,
        "api_calls": api_calls,
        "by_layer": layer_log,
    }


def strategy_no_cache(q: str) -> str:
    call_llm(q)
    return "API"


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("生产策略：分层缓存 vs 单层 vs 无缓存")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    print(f"负载：{len(WORKLOAD)} 个真实客服请求")
    print(f"   ~25% 完全重复  ~30% 同义改写  ~30% 全新  ~15% 危险（带否定/约束）")
    print()
    print(f"{Fore.YELLOW}本 demo 会真实调 API，预计 3-5 分钟{Style.RESET_ALL}\n")

    # 1. 无缓存基线
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"基线：无缓存（每次都调 API）")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    started = time.time()
    for i, q in enumerate(WORKLOAD, 1):
        call_llm(q)
        print(f"  [{i:2d}] {Fore.RED}API{Style.RESET_ALL}  {q}")
    no_cache_ms = int((time.time() - started) * 1000)

    # 2. 仅精确缓存
    exact_only = ExactCache()

    def fn_exact(q: str) -> str:
        cached = exact_only.get(q, MODEL_ID, 0.0)
        if cached is not None:
            return "EXACT"
        text, tokens, ms = call_llm(q)
        exact_only.put(q, MODEL_ID, 0.0, text, tokens, ms)
        return "API"

    exact_run = run_strategy("仅精确缓存", fn_exact)

    # 3. 分层（精确 + 语义）
    layered = LayeredCache(semantic_threshold=0.70)
    layered_run = run_strategy(
        "分层（精确 → 语义 → API），阈值 0.70",
        lambda q: layered.get_or_compute(q)[1],
    )

    # ---------- 总结 ----------
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("策略对比")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    print(f"  {'策略':<22} {'API 调用':>10} {'总耗时':>12} {'省了':>10}")
    print(f"  {'-'*22} {'-'*10} {'-'*12} {'-'*10}")

    print(f"  {'无缓存':<22} {len(WORKLOAD):>10} "
          f"{no_cache_ms:>10}ms  {'(基线)':>10}")

    saved_e = (no_cache_ms - exact_run["elapsed_ms"]) / no_cache_ms
    print(f"  {'精确缓存':<22} {exact_run['api_calls']:>10} "
          f"{exact_run['elapsed_ms']:>10}ms  "
          f"{Fore.GREEN}{saved_e*100:>8.0f}%{Style.RESET_ALL}")

    saved_l = (no_cache_ms - layered_run["elapsed_ms"]) / no_cache_ms
    print(f"  {'精确 + 语义（分层）':<22} {layered_run['api_calls']:>10} "
          f"{layered_run['elapsed_ms']:>10}ms  "
          f"{Fore.GREEN}{saved_l*100:>8.0f}%{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}分层缓存的命中分布：{Style.RESET_ALL}")
    s = layered.stats
    print(f"  精确层命中: {s.exact_hits}/{s.total} ({s.exact_hits/s.total*100:.0f}%)")
    print(f"  语义层命中: {s.semantic_hits}/{s.total} ({s.semantic_hits/s.total*100:.0f}%)")
    print(f"  API 调用 :  {s.misses}/{s.total} ({s.misses/s.total*100:.0f}%)")

    print(f"\n{Fore.YELLOW}观察要点：{Style.RESET_ALL}")
    print(f"  - 精确缓存吃掉了重复请求（零风险）")
    print(f"  - 语义缓存吃掉了'同义改写'（中等风险）")
    print(f"  - API 只为真正的'新问题'付费")
    print(f"  - 危险案例（'怎么不修改密码'）的处理结果你可以肉眼检查上面的 log")
    print()
    print(f"{Fore.GREEN}生产建议：{Style.RESET_ALL}")
    print(f"  1. 总是上精确缓存（零风险，永远值得）")
    print(f"  2. 语义阈值在自己数据上调（demo 用 0.70 仅供参考）+ 业务白名单（高风险问题不走语义层）")
    print(f"  3. 监控错答率：把命中的样本抽样过一遍，看错答率有没有飙升")
    print(f"  4. 别把缓存当唯一优化手段——慢的根因可能在 prompt 太长或模型选错")
    print()


if __name__ == "__main__":
    main()
