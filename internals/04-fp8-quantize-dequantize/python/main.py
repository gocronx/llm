"""main.py —— 可视化 FP8 vs Q8 量化的精度分布."""

from __future__ import annotations

import numpy as np
from quant import build_fp8_table, fp8_quantize_block_inplace, q8_roundtrip


def main() -> None:
    table = build_fp8_table()
    print(">>> FP8 E4M3FN 127 个可表示正值的间距 (注意非线性)")
    diffs = table[1:] - table[:-1]
    samples = [0, 8, 16, 32, 64, 96, 120]
    for i in samples:
        if i < len(diffs):
            print(f"   i={i:3d}: value={table[i]:>10.5f}  gap_to_next={diffs[i]:.5f}")
    print(
        "   ↑ 越大数 gap 越大 (exp 主导), 越小数 gap 越小 (mantissa 主导). 这是 FP8 香的原因."
    )

    print("\n>>> 量化随机 fp32 → 误差直方图")
    np.random.seed(0)
    x = np.random.randn(1024).astype(np.float32) * 10

    y_fp8 = fp8_quantize_block_inplace(x.copy(), block_size=64)
    y_q8 = q8_roundtrip(x.copy(), block_size=32)

    err_fp8 = np.abs(y_fp8 - x) / (np.abs(x) + 1e-6)
    err_q8 = np.abs(y_q8 - x) / (np.abs(x) + 1e-6)

    print(
        f"   FP8 block=64: P50={np.percentile(err_fp8, 50) * 100:.2f}%  P95={np.percentile(err_fp8, 95) * 100:.2f}%  max={err_fp8.max() * 100:.2f}%"
    )
    print(
        f"   Q8  block=32: P50={np.percentile(err_q8, 50) * 100:.2f}%  P95={np.percentile(err_q8, 95) * 100:.2f}%  max={err_q8.max() * 100:.2f}%"
    )

    print("\n>>> Outlier 场景: 63 个 small (σ=0.1) + 1 个 100.0")
    np.random.seed(0)
    block = np.concatenate([np.random.randn(63) * 0.1, np.array([100.0])]).astype(
        np.float32
    )
    y_fp8 = fp8_quantize_block_inplace(block.copy(), block_size=64)
    y_q8 = q8_roundtrip(block.copy(), block_size=64)
    print("   原 outlier value: 100.0")
    print(f"   FP8 还原: {y_fp8[-1]:.2f}  Q8 还原: {y_q8[-1]:.2f}")
    print(f"   原 small[0]: {block[0]:.4f}")
    print(f"   FP8 还原: {y_fp8[0]:.4f}  Q8 还原: {y_q8[0]:.4f}")
    print(
        "   ↑ Q8 scale 被 outlier 拉大, small values 损失大. FP8 用 exp 自适应, small 也保得住."
    )

    print("\n>>> 存储开销对比 (块大小 64)")
    n = 1024
    n_fp8_bytes = n * 1  # 1 byte / value (FP8 自带 dynamic range)
    n_q8_bytes = n * 1 + (n // 32) * 4  # 1 byte/value + 1 fp32 scale / 32 values
    n_fp16_bytes = n * 2
    print(f"   1024 个 fp16: {n_fp16_bytes} bytes")
    print(
        f"   1024 个 FP8:  {n_fp8_bytes} bytes  ({n_fp8_bytes * 100 / n_fp16_bytes:.0f}%)"
    )
    print(
        f"   1024 个 Q8:   {n_q8_bytes} bytes  ({n_q8_bytes * 100 / n_fp16_bytes:.0f}%)"
    )


if __name__ == "__main__":
    main()
