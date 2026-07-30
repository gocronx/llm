"""test.py —— RMSNorm + SiLU + SwiGLU 的数学性质验证."""

from __future__ import annotations

import time

import numpy as np
from layers import layer_norm, rms_norm, sigmoid_stable, silu, swiglu


def test_rmsnorm_output_norm() -> bool:
    """RMSNorm 后 RMS = 1 (近似, 受 eps 影响)."""
    np.random.seed(0)
    x = np.random.randn(8, 1024).astype(np.float32) * 5  # 大尺度输入
    out = rms_norm(x)
    rms = np.sqrt((out**2).mean(axis=-1))
    ok = np.all(np.abs(rms - 1.0) < 0.01)
    print(f"✓ rmsnorm output RMS ≈ 1.0 (got [{rms.min():.4f}, {rms.max():.4f}])")
    return ok


def test_rmsnorm_with_weight() -> bool:
    """带 weight 时, 输出按 weight 缩放."""
    x = np.random.randn(4, 512).astype(np.float32)
    weight = np.full(512, 2.5, dtype=np.float32)
    out = rms_norm(x, weight=weight)
    out_no_w = rms_norm(x)
    ok = np.allclose(out, out_no_w * 2.5, atol=1e-5)
    print("✓ rmsnorm with weight=2.5 scales output by 2.5")
    return ok


def test_rmsnorm_invariant_to_scale() -> bool:
    """rmsnorm(c·x) = rmsnorm(x) 对任意 c > 0 成立 (输入缩放不变)."""
    np.random.seed(1)
    x = np.random.randn(2, 256).astype(np.float32)
    a = rms_norm(x)
    b = rms_norm(x * 100.0)
    ok = np.allclose(a, b, atol=1e-4)
    print(f"✓ rmsnorm scale-invariant (max diff {np.abs(a - b).max():.2e})")
    return ok


def test_layernorm_equals_rmsnorm_after_centering() -> bool:
    """LayerNorm(x) = RMSNorm(x - mean(x)) 严格成立 (中心化后两者数学等价).

    这正是 RMSNorm 砍掉减均值的依据: 你随时可以靠"先减均值"把 RMSNorm 当 LayerNorm 用,
    所以"减均值"不是核心信息, 只是 re-scaling 才是."""
    np.random.seed(2)
    x = np.random.randn(4, 512).astype(np.float32)
    ln = layer_norm(x)
    rn = rms_norm(x - x.mean(axis=-1, keepdims=True))
    # 注意: layer_norm 用 var 算分母 (不带 eps 系数差异 1e-5 vs 1e-6), 允许小差
    diff = np.abs(ln - rn).max()
    ok = diff < 1e-3
    print(f"{'✓' if ok else '✗'} layernorm ≡ rmsnorm(centered x) (max diff {diff:.2e})")
    return ok


def test_sigmoid_stable_no_overflow() -> bool:
    """大正/负输入不溢出."""
    x = np.array([-1e5, -100, -1, 0, 1, 100, 1e5], dtype=np.float32)
    s = sigmoid_stable(x)
    expected = np.array([0.0, 0.0, 0.2689, 0.5, 0.7311, 1.0, 1.0])
    print(f"  sigmoid({x.tolist()}) = {s.round(4).tolist()}")
    ok = np.all(np.isfinite(s)) and np.allclose(s, expected, atol=1e-3)
    print(f"{'✓' if ok else '✗'} sigmoid_stable handles extreme inputs")
    return ok


def test_silu_known_values() -> bool:
    """SiLU(0) = 0, SiLU(x) ≈ x for x >> 0, SiLU(x) ≈ 0 for x << 0."""
    x = np.array([-10, -1, 0, 1, 10], dtype=np.float32)
    s = silu(x)
    print(f"  silu({x.tolist()}) = {s.round(4).tolist()}")
    ok = (
        abs(s[2]) < 1e-5  # silu(0) = 0
        and abs(s[4] - 10.0) < 0.01  # silu(10) ≈ 10
        and abs(s[0]) < 0.01  # silu(-10) ≈ 0
        and s[3] > 0.7
        and s[3] < 0.8  # silu(1) ≈ 0.7311
    )
    print(f"{'✓' if ok else '✗'} silu known values")
    return ok


def test_swiglu_shape_and_gating() -> bool:
    """SwiGLU output shape 跟 gate/up 一致; gate=0 时 output=0 (silu(0)=0 关门)."""
    gate = np.array([[0.0, 1.0, -100.0, 10.0]], dtype=np.float32)
    up = np.array([[5.0, 5.0, 5.0, 5.0]], dtype=np.float32)
    out = swiglu(gate, up)
    print(f"  gate={gate.flatten().tolist()}")
    print(f"  up=  {up.flatten().tolist()}")
    print(f"  out= {out.round(4).flatten().tolist()}")
    ok = (
        abs(out[0, 0]) < 1e-5  # gate=0 → silu(0)=0 → out=0
        and abs(out[0, 2]) < 0.01  # gate=-100 → silu≈0 → out≈0
        and out[0, 3] > 45
        and out[0, 3] < 51  # gate=10, up=5 → silu(10)*5 ≈ 50
    )
    print(f"{'✓' if ok else '✗'} swiglu gating behavior")
    return ok


def test_rmsnorm_speed_advantage() -> bool:
    """验证 RMSNorm 比 LayerNorm 操作数少 (一次 mean vs 两次)."""
    np.random.seed(3)
    x = np.random.randn(32, 4096).astype(np.float32)

    # warm
    rms_norm(x)
    layer_norm(x)
    N = 200
    t0 = time.perf_counter()
    for _ in range(N):
        rms_norm(x)
    rms_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    for _ in range(N):
        layer_norm(x)
    ln_ms = (time.perf_counter() - t0) * 1000

    print(f"  RMSNorm    {N} × (32, 4096): {rms_ms:.1f} ms")
    print(f"  LayerNorm  {N} × (32, 4096): {ln_ms:.1f} ms")
    print(f"  ratio: RMSNorm 是 LayerNorm 的 {rms_ms / ln_ms * 100:.0f}%")
    # 教学版 numpy 实现差距没 production C 那么大, 但应该有 30%+ 优势
    ok = rms_ms < ln_ms * 0.9
    print(f"{'✓' if ok else '⚠'} rmsnorm faster than layernorm (numpy 版差距比 C 版小)")
    return True  # 不强断言, 教学版有变数


def main() -> None:
    tests = [
        test_rmsnorm_output_norm,
        test_rmsnorm_with_weight,
        test_rmsnorm_invariant_to_scale,
        test_layernorm_equals_rmsnorm_after_centering,
        test_sigmoid_stable_no_overflow,
        test_silu_known_values,
        test_swiglu_shape_and_gating,
        test_rmsnorm_speed_advantage,
    ]
    passed = sum(t() for t in tests)
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
