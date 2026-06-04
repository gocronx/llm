"""main.py —— 可视化 SiLU / SwiGLU 曲线 + RMSNorm 缩放效果."""
from __future__ import annotations

import numpy as np

from layers import layer_norm, rms_norm, sigmoid_stable, silu, swiglu


def ascii_curve(x: np.ndarray, y: np.ndarray, height: int = 12, width: int = 60) -> str:
    """简易 ASCII 折线图."""
    y_min, y_max = float(y.min()), float(y.max())
    if y_max - y_min < 1e-9:
        return "(constant)"
    rows = []
    for r in range(height):
        target = y_max - (y_max - y_min) * r / (height - 1)
        row = ""
        for i in range(min(len(x), width)):
            scaled = (y[i] - y_min) / (y_max - y_min) * (height - 1)
            row += "*" if abs((height - 1 - scaled) - r) < 0.5 else " "
        rows.append(f"  {target:+.2f} | {row}")
    rows.append(f"          {'-' * width}")
    rows.append(f"          {x[0]:+.0f}{' ' * (width - 10)}{x[min(len(x), width) - 1]:+.0f}")
    return "\n".join(rows)


def main() -> None:
    x = np.linspace(-5, 5, 60)

    print(">>> sigmoid_stable(x)")
    print(ascii_curve(x, sigmoid_stable(x)))

    print("\n>>> silu(x) = x * sigmoid(x)")
    print(ascii_curve(x, silu(x)))

    print("\n>>> swiglu(gate, up) — 固定 up=2, 变 gate")
    gate = np.linspace(-5, 5, 60)
    up = np.full_like(gate, 2.0)
    print(ascii_curve(gate, swiglu(gate, up)))

    print("\n>>> RMSNorm vs LayerNorm 缩放不变性")
    np.random.seed(0)
    x_small = np.random.randn(1, 16).astype(np.float32)
    x_big = x_small * 100.0
    print(f"   输入 x_small (RMS={np.sqrt((x_small**2).mean()):.3f}):")
    print(f"     rms_norm: RMS = {np.sqrt((rms_norm(x_small)**2).mean()):.4f}")
    print(f"     layernorm: RMS = {np.sqrt((layer_norm(x_small)**2).mean()):.4f}")
    print(f"   输入 x_big = 100·x_small (RMS={np.sqrt((x_big**2).mean()):.3f}):")
    print(f"     rms_norm: RMS = {np.sqrt((rms_norm(x_big)**2).mean()):.4f}")
    print(f"     layernorm: RMS = {np.sqrt((layer_norm(x_big)**2).mean()):.4f}")
    print(f"   两个 RMS 都 ≈ 1, 跟输入幅度无关 → 这是 normalization 的核心")

    print("\n>>> 数值稳定 sigmoid: extreme 输入")
    print(f"   sigmoid_stable(-1e5) = {sigmoid_stable(np.array([-1e5]))[0]:.6e} (朴素版会 OOM)")
    print(f"   sigmoid_stable(+1e5) = {sigmoid_stable(np.array([+1e5]))[0]:.6f}")


if __name__ == "__main__":
    main()
