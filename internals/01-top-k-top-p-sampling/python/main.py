"""main.py —— demo only: 4 个 vocab=10 的玩具场景, 看不同参数下采样分布如何变.

每个场景 10000 次采样 → 统计直方图. 你能直接看出:
  - top_k=1 / temp=0 → 100% 集中在最高 logit 那个 id
  - top_p=0.5 → 只在累积概率 50% 内的几个 token 里采
  - min_p=0.3 → 砍掉相对最高太小的尾巴
  - temperature 高 → 接近均匀; 低 → 接近贪心
"""

from __future__ import annotations

from collections import Counter

import numpy as np
from sampling import sample, softmax

VOCAB = ["the", "a", "of", "to", "and", "in", "is", "that", "for", "rare"]
# 故意造一个有"长尾"的 logits 分布
LOGITS = np.array([4.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 0.0, -2.0])


def run(name: str, n: int = 10_000, **kw) -> None:
    rng = np.random.default_rng(42)
    counts = Counter()
    for _ in range(n):
        counts[sample(LOGITS, rng=rng, **kw)] += 1
    print(f"\n>>> {name} ({kw})")
    print(f"   分布: {dict((VOCAB[i], counts.get(i, 0)) for i in range(10))}")


def main() -> None:
    p = softmax(LOGITS, temperature=1.0)
    print(">>> 参考 softmax(temp=1) 概率:")
    for i, v in enumerate(p):
        print(f"   {VOCAB[i]:<5} {v:.4f}")

    run("temperature=1, 无过滤", temperature=1.0, top_k=0, top_p=1.0, min_p=0.0)
    run("temperature=0 (退化为贪心)", temperature=0.0)
    run("top_k=1 (也是贪心)", top_k=1)
    run("top_k=3", temperature=1.0, top_k=3, top_p=1.0, min_p=0.0)
    run("top_p=0.5", temperature=1.0, top_k=0, top_p=0.5, min_p=0.0)
    run("min_p=0.3 (砍长尾)", temperature=1.0, top_k=0, top_p=1.0, min_p=0.3)
    run(
        "low temperature=0.3 (接近贪心)", temperature=0.3, top_k=0, top_p=1.0, min_p=0.0
    )
    run(
        "high temperature=3.0 (接近均匀)",
        temperature=3.0,
        top_k=0,
        top_p=1.0,
        min_p=0.0,
    )


if __name__ == "__main__":
    main()
