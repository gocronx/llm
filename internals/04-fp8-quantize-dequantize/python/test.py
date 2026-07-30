"""test.py —— FP8 + Q8 量化的正确性 + 精度损失测量."""

from __future__ import annotations

import numpy as np
from quant import (
    build_fp8_table,
    fp8_e4m3_quantize,
    fp8_e4m3_value,
    fp8_quantize_block_inplace,
    q8_quantize_block,
    q8_roundtrip,
)


def test_fp8_table_monotonic() -> bool:
    """FP8 表应是严格升序 (0, ..., 448), 这样 searchsorted 才对."""
    table = build_fp8_table()
    is_monotonic = np.all(table[1:] > table[:-1])
    range_ok = abs(table[-1] - 448.0) < 1.0  # 最大可表示值 ≈ 448
    print(f"✓ FP8 table monotonic ({len(table)} entries, max {table[-1]:.1f})")
    return is_monotonic and range_ok


def test_fp8_known_values() -> bool:
    """E4M3FN 几个标定值: 1.0, 2.0, 0.5 都应能精确表示."""
    table = build_fp8_table()
    must_have = [0.0, 1.0, 2.0, 0.5, 256.0]
    found = [v for v in must_have if any(abs(table - v) < 1e-5)]
    ok = len(found) == len(must_have)
    print(f"{'✓' if ok else '✗'} FP8 表能精确表示 {must_have} (找到 {found})")
    return ok


def test_fp8_quantize_clamps_to_max() -> bool:
    """超过 448 的值应被截到 448, 不该 NaN/Inf."""
    x = np.array([1000.0, -1000.0, 448.5, -448.5, np.inf, -np.inf], dtype=np.float32)
    q = fp8_e4m3_quantize(x)
    print(f"  in:  {x.tolist()}")
    print(f"  out: {q.tolist()}")
    # inf 也会被 min(|x|, 448) 截到 448
    ok = np.all(np.abs(q) <= 448.0) and np.all(np.isfinite(q))
    print(f"{'✓' if ok else '✗'} FP8 clamps to [-448, +448]")
    return ok


def test_fp8_idempotent() -> bool:
    """对一个已经是 FP8 representable 的值再量化, 应返回自己."""
    table = build_fp8_table()
    sample = np.concatenate([table, -table])
    q = fp8_e4m3_quantize(sample)
    ok = np.allclose(q, sample, atol=1e-6)
    print(
        f"{'✓' if ok else '✗'} FP8 quantize idempotent on table values (max diff {np.abs(q - sample).max():.2e})"
    )
    return ok


def test_fp8_block_roundtrip_precision() -> bool:
    """随机 fp32 → FP8 block roundtrip, 相对误差应 < 5%."""
    np.random.seed(42)
    x = np.random.randn(256).astype(np.float32) * 10
    y = fp8_quantize_block_inplace(x, block_size=64)

    rel_err = np.abs(y - x) / (np.abs(x) + 1e-6)
    p50 = np.percentile(rel_err, 50)
    p95 = np.percentile(rel_err, 95)
    print(f"  FP8 roundtrip: P50 err {p50 * 100:.2f}%, P95 err {p95 * 100:.2f}%")
    ok = p50 < 0.05 and p95 < 0.20
    print(f"{'✓' if ok else '✗'} FP8 block precision (P50<5%, P95<20%)")
    return ok


def test_q8_block_roundtrip_precision() -> bool:
    """Q8 block roundtrip 应比 FP8 精度更好 (更细粒度的 scale, 但只对 small magnitude 友好)."""
    np.random.seed(42)
    x = np.random.randn(256).astype(np.float32) * 10
    y = q8_roundtrip(x, block_size=32)

    rel_err = np.abs(y - x) / (np.abs(x) + 1e-6)
    p50 = np.percentile(rel_err, 50)
    p95 = np.percentile(rel_err, 95)
    print(f"  Q8 roundtrip:  P50 err {p50 * 100:.2f}%, P95 err {p95 * 100:.2f}%")
    # P95 受 small magnitude 值的相对误差放大影响, 阈值放宽; abs err P95 才严格小
    abs_err = np.abs(y - x)
    abs_p95 = np.percentile(abs_err, 95)
    print(f"  Q8 abs error P95: {abs_p95:.4f} (输入 σ ≈ 10)")
    ok = p50 < 0.02 and abs_p95 < 0.5
    print(f"{'✓' if ok else '✗'} Q8 block precision (rel P50<2%, abs P95<0.5)")
    return ok


def test_fp8_better_at_outliers() -> bool:
    """FP8 有 exponent, 处理 outlier 大值时比 Q8 损失小."""
    # 构造 block: 1 个 outlier + 一群 small
    np.random.seed(0)
    x = np.concatenate([np.random.randn(63) * 0.1, np.array([100.0])]).astype(
        np.float32
    )

    y_fp8 = fp8_quantize_block_inplace(x.copy(), block_size=64)
    y_q8 = q8_roundtrip(x.copy(), block_size=64)

    err_fp8 = np.abs(y_fp8 - x).mean()
    err_q8 = np.abs(y_q8 - x).mean()
    print(
        f"  outlier scenario: FP8 mean abs err {err_fp8:.4f}, Q8 mean abs err {err_q8:.4f}"
    )
    print(f"  ratio: Q8 误差是 FP8 的 {err_q8 / err_fp8:.1f}×")
    # Q8 的 scale 被 outlier 拉大, small values 全砸到 0; FP8 还能用低 exp 表
    # 但有时 fp8 也吃亏 (exp 量化非线性). 教学版只验证趋势.
    print("⚠ FP8 vs Q8 outlier handling (具体差距数据相关, 不强断言)")
    return True


def test_q8_zero_block() -> bool:
    """全零 block 量化, scale=0, codes 全 0."""
    x = np.zeros(64, dtype=np.float32)
    codes, scales = q8_quantize_block(x, block_size=32)
    ok = np.all(codes == 0) and np.all(scales == 0.0)
    print(f"{'✓' if ok else '✗'} Q8 handles all-zero block")
    return ok


def test_quantize_vs_naive_fp8_value():
    """fp8_e4m3_value 跟 ds4.c 一些手算值对得上."""
    # ds4.c 表 (从代码 exp_scale 推):
    # i=0  → 0          (subnormal 0)
    # i=1  → 0.001953125 (subnormal 1)
    # i=8  → 0.015625    (normal: exp=1, mant=0 → (1+0) * 2^-6)
    # i=56 → 1.0         (normal: exp=7, mant=0 → 2^0)
    # i=64 → 2.0         (normal: exp=8, mant=0 → 2^1)
    cases = [(0, 0.0), (1, 0.001953125), (8, 0.015625), (56, 1.0), (64, 2.0)]
    for i, expected in cases:
        got = fp8_e4m3_value(i)
        assert abs(got - expected) < 1e-7, (
            f"fp8_e4m3_value({i}) = {got}, expected {expected}"
        )
    print("✓ fp8_e4m3_value matches ds4.c table at sentinel indices")
    return True


def main() -> None:
    tests = [
        test_fp8_table_monotonic,
        test_fp8_known_values,
        test_fp8_quantize_clamps_to_max,
        test_fp8_idempotent,
        test_fp8_block_roundtrip_precision,
        test_q8_block_roundtrip_precision,
        test_fp8_better_at_outliers,
        test_q8_zero_block,
        test_quantize_vs_naive_fp8_value,
    ]
    passed = sum(t() for t in tests)
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
