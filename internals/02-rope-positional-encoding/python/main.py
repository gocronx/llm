"""main.py —— demo: 可视化 RoPE 的相对位置编码性质.

绘 ASCII 图: 同一对 (q, k), 距离 d 从 0 到 N, 看内积的衰减曲线.
RoPE 不像绝对衰减 (cos 振荡), 但相关性会随距离而震荡-衰减."""
from __future__ import annotations

import numpy as np

from rope import apply_rope, apply_rope_yarn, dot_product


def ascii_bar(value: float, max_value: float, width: int = 40) -> str:
    n = int(abs(value) / max_value * width)
    side = "+" if value >= 0 else "-"
    return side * n


def main() -> None:
    np.random.seed(42)
    # 单 head, 64 维
    x = np.random.randn(1, 64).astype(np.float32)
    self_dot = dot_product(x, x)

    print(">>> RoPE 距离-相关性曲线 (单 head, head_dim=64)\n")
    print(f"   {'dist':>5} | {'correlation':>11} | bar")
    print("   " + "-" * 70)
    for d in [0, 1, 2, 5, 10, 20, 50, 100, 500, 1000]:
        q = apply_rope(x, pos=d)
        k = apply_rope(x, pos=0)
        corr = dot_product(q, k) / self_dot
        print(f"   {d:>5} | {corr:>11.4f} | {ascii_bar(corr, 1.0)}")

    print("\n>>> YaRN 长 context 外推 (训练 ctx=4096, 推理 ctx=32768)\n")
    print(f"   freq_scale = 4096 / 32768 = 0.125")
    print(f"   pos = 20000 (远超原训练范围)")
    for ext in [0.0, 0.5, 1.0]:
        out = apply_rope_yarn(x, pos=20000, n_ctx_orig=4096, freq_scale=0.125, ext_factor=ext)
        norm = np.linalg.norm(out)
        label = {0.0: "纯插值 PI", 0.5: "YaRN 中等混合", 1.0: "YaRN 完整"}[ext]
        print(f"   ext_factor={ext} ({label:<14}): out norm = {norm:.4f}, finite = {np.all(np.isfinite(out))}")

    print("\n>>> RoPE 在不同 pos 上的相位变化 (一个 (x0,x1) 对, freq_base=10000)")
    print(f"   freqs[0] (最高频) = {1.0:.6f} → 转 1 周期需要 {2*np.pi:.2f} 个 token")
    f_mid = 10000 ** (-32 / 64)   # i=32 (中间频段)
    print(f"   freqs[16] (中频)  = {f_mid:.6f} → 转 1 周期需要 {2*np.pi/f_mid:.2f} 个 token")
    f_low = 10000 ** (-62 / 64)
    print(f"   freqs[31] (最低频) = {f_low:.6f} → 转 1 周期需要 {2*np.pi/f_low:.2f} 个 token")
    print(f"\n   ↑ 高频维度编码近距离 (周期短), 低频维度编码远距离 (周期长)")


if __name__ == "__main__":
    main()
