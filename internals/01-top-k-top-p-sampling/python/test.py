"""test.py —— 采样算法的正确性验证. 重点是退化路径 + 分布逼近."""
from __future__ import annotations

from collections import Counter

import numpy as np

from sampling import sample, softmax


def test_temperature_zero_is_argmax() -> bool:
    logits = np.array([1.0, 5.0, 3.0, 4.0])
    rng = np.random.default_rng(0)
    out = {sample(logits, temperature=0.0, rng=rng) for _ in range(50)}
    ok = out == {1}  # logits[1]=5 最大
    print(f"{'✓' if ok else '✗'} temperature=0 → argmax (got {out})")
    return ok


def test_top_k_one_is_argmax() -> bool:
    logits = np.array([1.0, 5.0, 3.0, 4.0])
    rng = np.random.default_rng(0)
    out = {sample(logits, top_k=1, rng=rng) for _ in range(50)}
    ok = out == {1}
    print(f"{'✓' if ok else '✗'} top_k=1 → argmax (got {out})")
    return ok


def test_top_p_small_narrows() -> bool:
    """top_p=0.5 应该只在头部几个 token 里采."""
    logits = np.array([4.0, 3.0, 2.0, 1.0, 0.0])
    p = softmax(logits, 1.0)
    # 累积到 0.5 大概只覆盖前 1-2 个
    rng = np.random.default_rng(0)
    out = Counter(sample(logits, temperature=1.0, top_k=0, top_p=0.5, min_p=0.0, rng=rng)
                  for _ in range(2000))
    ok = max(out.keys()) <= 2  # 应该集中在 id 0, 1, 最多 2
    print(f"{'✓' if ok else '✗'} top_p=0.5 narrows (used ids {sorted(out)}, ref probs {p.round(3)})")
    return ok


def test_min_p_filters_long_tail() -> bool:
    """min_p=0.5 应该排除概率 < probs[0]*0.5 的 token."""
    logits = np.array([5.0, 4.0, 1.0, 0.0, -1.0])
    rng = np.random.default_rng(0)
    out = Counter(sample(logits, temperature=1.0, top_k=0, top_p=1.0, min_p=0.5, rng=rng)
                  for _ in range(2000))
    # logits[0]=5, logits[1]=4 (差 1, e^-1 ≈ 0.37 < 0.5 阈值)
    # 实际上 probs_norm[1] / probs_norm[0] = e^-1 ≈ 0.367, 应该被 min_p=0.5 砍掉
    ok = sorted(out.keys()) == [0]
    print(f"{'✓' if ok else '✗'} min_p=0.5 long tail (used ids {sorted(out)})")
    return ok


def test_pure_softmax_distribution() -> bool:
    """top_k=0, top_p=1, min_p=0 应该等价于纯 softmax 多项采样, 大样本下分布应逼近."""
    logits = np.array([2.0, 1.0, 0.5, 0.0, -1.0])
    p_ref = softmax(logits, 1.0)
    N = 20_000
    rng = np.random.default_rng(123)
    cnt = Counter(sample(logits, temperature=1.0, top_k=0, top_p=1.0, min_p=0.0, rng=rng)
                  for _ in range(N))
    p_emp = np.array([cnt.get(i, 0) / N for i in range(5)])
    # L1 距离应 < 0.02 (经验值, N=20k 够稳)
    l1 = np.abs(p_emp - p_ref).sum()
    ok = l1 < 0.03
    print(f"{'✓' if ok else '✗'} pure softmax distribution (L1={l1:.4f}, ref={p_ref.round(3)}, emp={p_emp.round(3)})")
    return ok


def test_non_finite_logits_skipped() -> bool:
    """有 -inf / NaN 的 logits 不该污染 softmax."""
    logits = np.array([1.0, np.nan, 3.0, -np.inf, 2.0])
    rng = np.random.default_rng(0)
    out = {sample(logits, temperature=1.0, top_k=0, top_p=1.0, min_p=0.0, rng=rng) for _ in range(500)}
    # 只应该在 {0, 2, 4} 中, NaN 和 -inf 不应被选
    ok = out.issubset({0, 2, 4}) and len(out) >= 2
    print(f"{'✓' if ok else '✗'} non-finite skipped (got {out})")
    return ok


def test_top_p_keeps_at_least_one() -> bool:
    """极小 top_p 也至少给 1 个候选, 不会返回 -1."""
    logits = np.array([5.0, 4.0, 3.0, 2.0])
    rng = np.random.default_rng(0)
    out = {sample(logits, temperature=1.0, top_k=0, top_p=1e-6, min_p=0.0, rng=rng) for _ in range(50)}
    ok = out == {0}  # 至少保留最高 logit 那个
    print(f"{'✓' if ok else '✗'} top_p tiny keeps at least 1 (got {out})")
    return ok


def test_high_temperature_uniform() -> bool:
    """temp=100 时分布应接近均匀."""
    logits = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
    N = 10_000
    rng = np.random.default_rng(0)
    cnt = Counter(sample(logits, temperature=100.0, top_k=0, top_p=1.0, min_p=0.0, rng=rng)
                  for _ in range(N))
    p_emp = np.array([cnt.get(i, 0) / N for i in range(5)])
    # 跟 0.2 (1/5) 的距离应该不大
    l1 = np.abs(p_emp - 0.2).sum()
    ok = l1 < 0.05
    print(f"{'✓' if ok else '✗'} high temperature ~ uniform (L1={l1:.4f}, emp={p_emp.round(3)})")
    return ok


def main() -> None:
    tests = [
        test_temperature_zero_is_argmax,
        test_top_k_one_is_argmax,
        test_top_p_small_narrows,
        test_min_p_filters_long_tail,
        test_pure_softmax_distribution,
        test_non_finite_logits_skipped,
        test_top_p_keeps_at_least_one,
        test_high_temperature_uniform,
    ]
    passed = sum(t() for t in tests)
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
