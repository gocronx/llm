"""
快速入门：三种缓存对比，跑一次就能直观理解差别

跑同一组真实负载，分别用：
  1. 无缓存（基线）
  2. 精确缓存
  3. 语义缓存
对比：调用次数、耗时、命中率。

跑完你会知道：
  - 精确缓存：稳，但命中率取决于"用户是否说一模一样的话"
  - 语义缓存：命中率高，但有误命中风险
"""

import time
from colorama import Fore, Style, init

from exact_cache import ExactCache, call_with_cache as call_exact
from semantic_cache import SemanticCache, call_with_semantic_cache

init(autoreset=True)


# 模拟一个客服场景：5 个真实问题被用不同方式问了 8 次
WORKLOAD = [
    "怎么修改账号密码？",
    "如何修改账号密码",          # 与第 1 句几乎相同（语义缓存能命中）
    "我想改下密码该怎么操作",    # 同义改写（语义缓存可能命中）
    "怎么申请退款",              # 新问题
    "退款怎么办理",              # 与上句同义
    "订单什么时候发货",          # 新问题
    "怎么修改账号密码？",        # 精确重复第 1 句（精确缓存能命中）
    "今天有什么优惠活动",        # 新问题
]


def run_no_cache():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("基线：无缓存（每次都调真实 API）")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    from exact_cache import call_llm
    started = time.time()
    api_calls = 0
    for i, q in enumerate(WORKLOAD, 1):
        text, tokens, ms = call_llm(q)
        api_calls += 1
        print(f"  [{i}] {Fore.YELLOW}API CALL{Style.RESET_ALL} ({ms:>5d}ms)  {q}")

    total_ms = int((time.time() - started) * 1000)
    return {"api_calls": api_calls, "total_ms": total_ms}


def run_exact():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("方法 A：精确缓存（SHA256 哈希 prompt）")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    cache = ExactCache()
    started = time.time()
    api_calls = 0
    for i, q in enumerate(WORKLOAD, 1):
        text, hit, ms = call_exact(q, cache)
        if not hit:
            api_calls += 1
        mark = f"{Fore.GREEN}HIT " if hit else f"{Fore.YELLOW}MISS"
        print(f"  [{i}] {mark}{Style.RESET_ALL} ({ms:>5d}ms)  {q}")

    total_ms = int((time.time() - started) * 1000)
    return {
        "api_calls": api_calls,
        "total_ms": total_ms,
        "hit_rate": cache.stats.hit_rate,
    }


def run_semantic():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("方法 B：语义缓存（n-gram + Jaccard, 阈值 0.55）")
    print(f"{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}注：此阈值偏激进，仅为演示同义命中。生产环境会显著提高误命中率。{Style.RESET_ALL}\n")

    cache = SemanticCache(threshold=0.55)
    started = time.time()
    api_calls = 0
    for i, q in enumerate(WORKLOAD, 1):
        text, hit, info, ms = call_with_semantic_cache(q, cache)
        if not hit:
            api_calls += 1
        if hit:
            original, score = info
            mark = f"{Fore.GREEN}HIT "
            extra = f"  ← 命中 '{original}' (sim={score:.2f})"
        else:
            mark = f"{Fore.YELLOW}MISS"
            extra = ""
        print(f"  [{i}] {mark}{Style.RESET_ALL} ({ms:>5d}ms)  {q}{extra}")

    total_ms = int((time.time() - started) * 1000)
    return {
        "api_calls": api_calls,
        "total_ms": total_ms,
        "hit_rate": cache.stats.hit_rate,
    }


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("缓存对比：无缓存 vs 精确 vs 语义")
    print(f"{'='*60}{Style.RESET_ALL}")
    print(f"\n负载：{len(WORKLOAD)} 个客服问题（部分重复 / 部分同义改写）")
    print(f"模型：本地 MLX")
    print(f"\n{Fore.YELLOW}注意：本 demo 会真实调 API，预计耗时 1-3 分钟{Style.RESET_ALL}\n")

    baseline = run_no_cache()
    exact = run_exact()
    semantic = run_semantic()

    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("对比结果")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    print(f"  {'方案':<12} {'API 调用':>10} {'总耗时':>12} {'省了':>10}")
    print(f"  {'-'*12} {'-'*10} {'-'*12} {'-'*10}")
    print(f"  {'无缓存':<12} {baseline['api_calls']:>10}  "
          f"{baseline['total_ms']:>10}ms  {'(基线)':>10}")

    saved_e = baseline["total_ms"] - exact["total_ms"]
    saved_s = baseline["total_ms"] - semantic["total_ms"]
    print(f"  {'精确缓存':<12} {exact['api_calls']:>10}  "
          f"{exact['total_ms']:>10}ms  "
          f"{Fore.GREEN}{saved_e/baseline['total_ms']*100:>8.0f}%{Style.RESET_ALL}")
    print(f"  {'语义缓存':<12} {semantic['api_calls']:>10}  "
          f"{semantic['total_ms']:>10}ms  "
          f"{Fore.GREEN}{saved_s/baseline['total_ms']*100:>8.0f}%{Style.RESET_ALL}")

    print(f"\n  命中率：精确 {exact['hit_rate']*100:.0f}%   "
          f"语义 {semantic['hit_rate']*100:.0f}%")

    print(f"\n{Fore.YELLOW}观察要点：{Style.RESET_ALL}")
    print(f"  - 精确缓存只命中真正一字不差的重复（'怎么修改账号密码？' 那条）")
    print(f"  - 语义缓存还能命中同义改写，所以省得更多")
    print(f"  - 但语义缓存的代价是：可能在你看不到的地方'误命中'返回错答案")
    print(f"  - 看 semantic_cache.py 演示 4 看危险案例")
    print()
    print(f"{Fore.CYAN}下一步：{Style.RESET_ALL}")
    print(f"  python exact_cache.py        # 精确缓存的 4 个细节演示")
    print(f"  python semantic_cache.py     # 语义缓存 + 阈值权衡 + 危险案例")
    print(f"  python prefix_cache.py       # 服务端前缀缓存（不同层次）")
    print(f"  python production_example.py # 生产策略：分层组合")
    print()


if __name__ == "__main__":
    main()
