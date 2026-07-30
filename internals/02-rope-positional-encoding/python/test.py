"""test.py —— 验证 RoPE 的核心性质. 不依赖任何模型."""
from __future__ import annotations

import numpy as np
from rope import apply_rope, apply_rope_yarn, dot_product, precompute_freqs


def test_pos_zero_is_identity() -> bool:
    """pos=0 时, cos(0)=1 sin(0)=0, RoPE 应当不改变输入."""
    x = np.random.randn(4, 64).astype(np.float32)
    out = apply_rope(x, pos=0)
    ok = np.allclose(out, x, atol=1e-5)
    print(f"{'✓' if ok else '✗'} pos=0 is identity (max diff {np.abs(out-x).max():.2e})")
    return ok


def test_norm_preserved() -> bool:
    """旋转矩阵正交, RoPE 应保留 L2 范数."""
    x = np.random.randn(4, 64).astype(np.float32)
    for pos in [1, 17, 1000]:
        out = apply_rope(x, pos=pos)
        n_before = np.linalg.norm(x)
        n_after = np.linalg.norm(out)
        assert np.allclose(n_before, n_after, rtol=1e-4), f"pos={pos} norm changed: {n_before} -> {n_after}"
    print(f"✓ norm preserved across positions")
    return True


def test_inverse_undoes_rope() -> bool:
    """apply 一次 + apply inverse=True 应当还原原值."""
    x = np.random.randn(4, 64).astype(np.float32)
    rotated = apply_rope(x, pos=42)
    back = apply_rope(rotated, pos=42, inverse=True)
    ok = np.allclose(back, x, atol=1e-4)
    print(f"{'✓' if ok else '✗'} inverse undoes rotation (max diff {np.abs(back-x).max():.2e})")
    return ok


def test_relative_position_dot_product() -> bool:
    """RoPE 的核心性质: <RoPE(q, m), RoPE(k, n)> 只依赖 (m-n).

    具体: 对同一对 (q, k), 不同绝对位置但相同距离的内积应当一致."""
    np.random.seed(0)
    q = np.random.randn(1, 64).astype(np.float32)
    k = np.random.randn(1, 64).astype(np.float32)

    # 距离 = 5, 绝对位置不同
    dots = []
    for base in [0, 100, 1000]:
        q_at_m = apply_rope(q, pos=base + 5)
        k_at_n = apply_rope(k, pos=base + 0)
        dots.append(dot_product(q_at_m, k_at_n))

    # 三个距离=5 的内积应当几乎相等
    spread = max(dots) - min(dots)
    ok = spread < 1e-3
    print(f"✓ relative position: dot products at distance=5 = {[f'{d:.4f}' for d in dots]}, spread={spread:.2e}")
    return ok


def test_far_distance_smaller_correlation() -> bool:
    """距离越远, 同样的 q,k 内积**平均**越接近 0 (RoPE 的震荡-衰减性质, 非单调).

    RoPE 不是绝对衰减 (cos 本身震荡), 但低频维度在远距离上会持续散开,
    所以 **多 sample 平均** 的 correlation 会随距离变小."""
    np.random.seed(1)
    # 用同一个向量做 q 和 k, pos=0 时 correlation = 1 (自相关)
    x = np.random.randn(1, 64).astype(np.float32)
    self_dot = dot_product(x, x)

    # 取一组距离, 各采样几个起点, 求平均
    def mean_corr_at_distance(d: int, n_samples: int = 5) -> float:
        vals = []
        for base in [0, 50, 100, 200, 500]:
            q = apply_rope(x, pos=base + d)
            k = apply_rope(x, pos=base)
            vals.append(dot_product(q, k) / self_dot)
        return float(np.mean(np.abs(vals)))

    distances = [0, 1, 10, 100, 1000]
    avg_corrs = [mean_corr_at_distance(d) for d in distances]
    print(f"  distance -> |avg corr|: {list(zip(distances, [f'{c:.3f}' for c in avg_corrs]))}")

    ok = avg_corrs[0] > 0.99 and avg_corrs[-1] < avg_corrs[0] - 0.3   # d=1000 比 d=0 至少跌 0.3
    print(f"{'✓' if ok else '✗'} far distance reduces avg correlation")
    return ok


def test_yarn_long_context_does_not_explode() -> bool:
    """朴素外推到训练 context 的 8 倍时, sin/cos 的相位是良性的 (不会因 theta 太大溢出).

    YaRN 比朴素外推更好的地方在于"分布对齐", 但教学版只验证数值健康."""
    n_ctx_orig = 4096
    target = 32768
    freq_scale = n_ctx_orig / target  # 1/8

    x = np.random.randn(2, 64).astype(np.float32)

    # 在 pos=20000 (远超原训练 ctx) 应用 YaRN
    out_yarn = apply_rope_yarn(x, pos=20000, n_ctx_orig=n_ctx_orig, freq_scale=freq_scale)
    out_plain = apply_rope(x, pos=20000)

    yarn_finite = np.all(np.isfinite(out_yarn))
    plain_finite = np.all(np.isfinite(out_plain))   # plain RoPE 在这位置也不会溢出 (cos/sin 有界)
    print(f"  YaRN @ pos=20000: norm={np.linalg.norm(out_yarn):.4f}, finite={yarn_finite}")
    print(f"  plain @ pos=20000: norm={np.linalg.norm(out_plain):.4f}, finite={plain_finite}")
    ok = yarn_finite and plain_finite
    print(f"{'✓' if ok else '✗'} numerically healthy at far positions")
    return ok


def test_yarn_pi_equivalent_when_ext_zero() -> bool:
    """ext_factor=0 时 YaRN 退化为朴素位置插值 (PI), 等价于 theta * freq_scale."""
    x = np.random.randn(2, 32).astype(np.float32)

    yarn_pi = apply_rope_yarn(x, pos=1000, freq_scale=0.25, ext_factor=0.0)
    # 等价手算: 用 freq_scale 缩放 pos, 应等同于 apply_rope(x, pos=pos*freq_scale)
    plain_scaled = apply_rope(x, pos=int(1000 * 0.25))
    # 注意 pos 是 int, freq_scale=0.25 时 plain 用 pos=250
    # YaRN 内部 theta = 0.25 * 1000 * freq = 250 * freq, 跟 plain pos=250 等价
    ok = np.allclose(yarn_pi, plain_scaled, atol=1e-4)
    print(f"{'✓' if ok else '✗'} YaRN ext_factor=0 ≡ pure PI (max diff {np.abs(yarn_pi-plain_scaled).max():.2e})")
    return ok


def main() -> None:
    tests = [
        test_pos_zero_is_identity,
        test_norm_preserved,
        test_inverse_undoes_rope,
        test_relative_position_dot_product,
        test_far_distance_smaller_correlation,
        test_yarn_long_context_does_not_explode,
        test_yarn_pi_equivalent_when_ext_zero,
    ]
    passed = sum(t() for t in tests)
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
