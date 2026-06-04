"""main.py —— 演示投机解码的加速比 (随 draft accuracy 和 lookahead 变).

模拟 target 比 draft 慢 10× 的现实情景, 输出 wall-clock 比对."""
from __future__ import annotations

import time

from speculative import (
    make_draft,
    make_target,
    naive_decode,
    speculative_decode,
)


# 模拟 target/draft 的执行时间 (真实是 GPU forward, 这里用 sleep 近似)
TARGET_MS = 10.0   # 70B 大模型一次 forward
DRAFT_MS = 1.0     # 小 draft 模型 / MTP head


def timed(fn, *args, **kw):
    t0 = time.perf_counter()
    out = fn(*args, **kw)
    return out, (time.perf_counter() - t0) * 1000


def main() -> None:
    n_steps = 50
    prefix = [1, 2, 3]

    target = make_target(seed=2025)

    print(f">>> 任务: 生成 {n_steps} 个 token (vocab=100)")
    print(f"   假设 target forward = {TARGET_MS} ms, draft forward = {DRAFT_MS} ms")
    print(f"   wall-clock 用 stats × 时间常量估算, 不真 sleep (避免测试太慢)\n")

    # 朴素 baseline
    _, naive_stats = naive_decode(prefix, n_steps, target)
    naive_wall = naive_stats.target_calls * TARGET_MS
    print(f"朴素自回归:")
    print(f"   target_calls = {naive_stats.target_calls}")
    print(f"   预估 wall-clock = {naive_wall:.1f} ms")
    print(f"   = {n_steps * 1000 / naive_wall:.1f} token/s")
    print()

    print(f"{'draft acc':<10} {'lookahead':<10} {'target_calls':<14} {'draft_calls':<13} {'accept_rate':<13} {'wall_ms':<10} {'speedup':<10}")
    print("-" * 90)

    for accuracy in [0.5, 0.7, 0.9]:
        draft = make_draft(target, accuracy=accuracy)
        for K in [2, 4, 8]:
            _, stats = speculative_decode(prefix, n_steps, target, draft, lookahead=K)
            wall = stats.target_calls * TARGET_MS + stats.draft_calls * DRAFT_MS
            speedup = naive_wall / wall
            accept_rate = stats.accepted / max(1, stats.accepted + stats.rejected)
            print(f"{accuracy:<10} {K:<10} {stats.target_calls:<14} {stats.draft_calls:<13} "
                  f"{accept_rate:<13.2f} {wall:<10.1f} {speedup:<10.2f}×")

    print("\n>>> 启用 margin filter (margin_threshold=1.5)")
    print(f"{'draft acc':<10} {'lookahead':<10} {'target_calls':<14} {'margin_filtered':<17} {'wall_ms':<10} {'speedup':<10}")
    print("-" * 90)
    for accuracy in [0.5, 0.7]:
        draft = make_draft(target, accuracy=accuracy)
        for K in [4, 8]:
            _, stats = speculative_decode(prefix, n_steps, target, draft, lookahead=K, margin_threshold=1.5)
            wall = stats.target_calls * TARGET_MS + stats.draft_calls * DRAFT_MS
            speedup = naive_wall / wall
            print(f"{accuracy:<10} {K:<10} {stats.target_calls:<14} {stats.margin_filtered:<17} "
                  f"{wall:<10.1f} {speedup:<10.2f}×")


if __name__ == "__main__":
    main()
