"""main.py —— demo only：在一组混合难度 query 上对照五种路由策略。"""

import argparse

from models import REGISTRY
from router import (
    RouteResult, route_always, route_cascade, route_classifier, route_rules,
)


QUERIES = [
    "你好",
    "1+1 等于几？",
    "Translate 'hello world' to Chinese.",
    "用 Python 写一个函数，把字符串里的所有数字提取出来。",
    "用一段话总结：人工智能的快速发展引发了广泛讨论。支持者认为它将提升生产力。",
    "请详细分析 Raft 共识算法的 leader election 过程，包括 split vote 怎么处理。",
    "Design a distributed cache with TTL, LRU eviction, and consistency under concurrent writes. "
    "Cover the partitioning scheme, replication, and how reads behave during node failure.",
]


STRATEGIES = {
    "always-cheap":   lambda q: route_always("cheap", q),
    "always-premium": lambda q: route_always("premium", q),
    "rules":          route_rules,
    "classifier":     route_classifier,
    "cascade":        route_cascade,
}


def _fmt(r: RouteResult) -> str:
    head = f"{r.chosen.tier:<7} {r.elapsed_ms:>5}ms  ${r.cost:.5f}"
    if r.escalated_from:
        head += f"  [escalated from {r.escalated_from.tier}]"
    if r.failed_over_from:
        tiers = ",".join(m.tier for m in r.failed_over_from)
        head += f"  [failed over from {tiers}]"
    return head


def _print_registry() -> None:
    print("Registered models:")
    for m in REGISTRY:
        print(f"  {m.tier:<7} {m.id:<70} ${m.input_per_1k:.5f}/k in  ${m.output_per_1k:.5f}/k out  q={m.quality}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="all",
                        choices=["all", *STRATEGIES])
    parser.add_argument("--limit", type=int, default=len(QUERIES))
    args = parser.parse_args()

    _print_registry()
    queries = QUERIES[: args.limit]
    selected = STRATEGIES if args.strategy == "all" else {args.strategy: STRATEGIES[args.strategy]}

    for name, fn in selected.items():
        print(f"\n=== {name} ===")
        total_cost = total_ms = 0
        for i, q in enumerate(queries, 1):
            try:
                r = fn(q)
                total_cost += r.cost
                total_ms += r.elapsed_ms
                print(f"  [{i}] {_fmt(r)}  {q[:48]}")
            except Exception as e:
                print(f"  [{i}] ERROR {type(e).__name__}: {e}")
        print(f"  total: {total_ms}ms  ${total_cost:.5f}")


if __name__ == "__main__":
    main()
