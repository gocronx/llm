"""rope.py —— Rotary Position Embedding + YaRN 长 context 外推.

抽自 ds4.c:4675-4742 (rope_tail_ext_inplace). 是 LLaMA/DeepSeek/Qwen 系列 LLM 的标配位置编码.

## RoPE 的几何直觉

把 head_dim 维向量按 (x0,x1), (x2,x3), ... 两两配对, 每对看成复数 `x0 + i*x1`.
位置 pos 的 token 在第 (i, i+1) 维上乘旋转因子 `exp(i*theta_i)`:

  x0' = x0*cos(theta) - x1*sin(theta)     ← 复数乘法的实部
  x1' = x0*sin(theta) + x1*cos(theta)     ← 复数乘法的虚部

其中 `theta_i = pos / (freq_base^(2i/n_rot))`, 不同 i 用不同频率.

## 为什么这样设计

- **相对位置编码**: q (pos=m) · k (pos=n) 只依赖 (m-n), 因为旋转向量内积有这性质
- **频率分层**: 低 i (高频, 转得快) → 编码近距离关系; 高 i (低频, 转得慢) → 编码远距离
- **可外推**: pos 是连续的, 训练时见过的 pos=0..L 在推理时可外推到 pos=2L (但通常会偏移, 需 YaRN 修正)

## YaRN —— 长 context 外推

训练用 pos ∈ [0, 4096], 推理想用 pos ∈ [0, 32768] 怎么办?

- 朴素**插值** (PI): 把 pos 缩到训练范围, `theta = (pos / scale) * freq_base^(-2i/n_rot)`
  → 长 context OK, 但近距离精度损失
- 朴素**外推**: theta 不变直接外推 → 训练分布外, 模型崩
- **YaRN 混合**: 高频 (i 小, 转得快) 不变直接外推 (保近距离精度); 低频 (i 大) 用插值 (扩远距离)
  → `corr_dims[low, high]` 定义高/低频边界, 用 `ramp(i)` 函数平滑过渡

## 关键工程细节

1. **每两个维度一组**: 不是 head_dim 整个旋转, 是 (0,1) (2,3) ... 配对
2. **freq_base 通常 10000 或 500000**: 大 base → 频率分布更分散, 长 context 友好
3. **mscale (attention scaling)**: YaRN 外推时配合 attention logit 缩放, 防止 softmax 太尖
4. **NoPE 部分**: 某些模型 (DS4) head_dim 前部分不用 RoPE, 只对 tail 用; 教学版我们对全部做
"""

from __future__ import annotations

import numpy as np


def precompute_freqs(n_rot: int, freq_base: float = 10000.0) -> np.ndarray:
    """预计算 n_rot/2 个频率: freqs[i] = 1 / freq_base^(2i/n_rot).

    这些频率不依赖 pos, 一次算好喂给所有 token. 真生产里会跟 head_dim 解耦预算, 教学版每次现算."""
    i = np.arange(0, n_rot, 2, dtype=np.float32)  # 0, 2, 4, ..., n_rot-2
    return 1.0 / np.power(freq_base, i / n_rot)


def apply_rope(
    x: np.ndarray,  # shape (n_head, head_dim), 一个 token 的 q 或 k
    pos: int,
    freqs: np.ndarray | None = None,
    freq_base: float = 10000.0,
    inverse: bool = False,
) -> np.ndarray:
    """对一个 token 的 q 或 k 矩阵应用 RoPE. 返回新数组 (不改入参).

    pos: token 在序列中的位置 (0-indexed)
    inverse: True 则反向旋转 (-theta), 用于 attention output 还原
    """
    n_head, head_dim = x.shape
    if head_dim % 2 != 0:
        raise ValueError(f"head_dim must be even, got {head_dim}")
    n_rot = head_dim  # 教学版: 整个 head_dim 都旋转

    if freqs is None:
        freqs = precompute_freqs(n_rot, freq_base)

    # theta[i] = pos * freqs[i], shape (n_rot/2,)
    theta = pos * freqs
    if inverse:
        theta = -theta

    cos_t = np.cos(theta)
    sin_t = np.sin(theta)

    # 把 x 按 (x0,x1) (x2,x3) ... 重排成 (n_head, n_rot/2, 2)
    x_pair = x.reshape(n_head, n_rot // 2, 2)
    x0 = x_pair[..., 0]
    x1 = x_pair[..., 1]
    # 复数乘法: (x0 + i*x1) * (cos + i*sin) = (x0*cos - x1*sin) + i*(x0*sin + x1*cos)
    new_x0 = x0 * cos_t - x1 * sin_t
    new_x1 = x0 * sin_t + x1 * cos_t

    out = np.stack([new_x0, new_x1], axis=-1).reshape(n_head, head_dim)
    return out.astype(x.dtype)


# ----- YaRN 扩展 -----


def yarn_corr_dim(
    n_dims: int, n_ctx_orig: int, n_rot_at_period: float, freq_base: float
) -> float:
    """计算"周期=n_rot_at_period 个 token"对应的维度位置 i.

    用 beta_fast/beta_slow 两个周期阈值找出 corr_dims[low, high]:
      - i < low: 高频 (周期短于 beta_fast 个 token), YaRN 走外推路径
      - i > high: 低频 (周期长于 beta_slow 个 token), YaRN 走插值路径
      - low <= i <= high: 平滑过渡
    """
    return (
        n_dims
        * np.log(n_ctx_orig / (n_rot_at_period * 2.0 * np.pi))
        / (2.0 * np.log(freq_base))
    )


def yarn_corr_dims(
    n_dims: int, n_ctx_orig: int, freq_base: float, beta_fast: float, beta_slow: float
) -> tuple[float, float]:
    low = max(0.0, np.floor(yarn_corr_dim(n_dims, n_ctx_orig, beta_fast, freq_base)))
    high = min(
        float(n_dims - 1),
        np.ceil(yarn_corr_dim(n_dims, n_ctx_orig, beta_slow, freq_base)),
    )
    return float(low), float(high)


def yarn_ramp(low: float, high: float, i0: int) -> float:
    """i=i0 处的"插值 vs 外推"混合比例. 返回值 ∈ [0, 1], 1=纯外推, 0=纯插值."""
    y = (i0 / 2 - low) / max(0.001, high - low)
    return 1.0 - min(1.0, max(0.0, y))


def apply_rope_yarn(
    x: np.ndarray,
    pos: int,
    n_ctx_orig: int = 4096,  # 训练时的 context 长度
    freq_base: float = 10000.0,
    freq_scale: float = 1.0,  # = n_ctx_orig / target_ctx, e.g. 4096/32768 = 0.125
    ext_factor: float = 1.0,  # 1=用 YaRN 混合, 0=纯插值 (PI)
    attn_factor: float = 1.0,
    beta_fast: float = 32.0,
    beta_slow: float = 1.0,
    inverse: bool = False,
) -> np.ndarray:
    """YaRN 版 RoPE: 高频维度直接外推, 低频维度插值, 中间平滑混合.

    教学版砍掉的: NoPE 头部 (DS4 特性), 多种 ramp 函数变体. 保留核心混合逻辑.
    """
    n_head, head_dim = x.shape
    n_rot = head_dim

    corr_dims = (
        yarn_corr_dims(n_rot, n_ctx_orig, freq_base, beta_fast, beta_slow)
        if ext_factor != 0
        else (0.0, 0.0)
    )
    sin_sign = -1.0 if inverse else 1.0

    out = np.empty_like(x)
    freqs = precompute_freqs(n_rot, freq_base)

    for h in range(n_head):
        for i_pair in range(n_rot // 2):
            i = i_pair * 2
            theta_extrap = pos * freqs[i_pair]
            theta_interp = freq_scale * theta_extrap

            if ext_factor != 0.0:
                ramp_mix = yarn_ramp(corr_dims[0], corr_dims[1], i) * ext_factor
                theta = theta_interp * (1.0 - ramp_mix) + theta_extrap * ramp_mix
                mscale = attn_factor * (1.0 + 0.1 * np.log(1.0 / freq_scale))
            else:
                theta = theta_interp
                mscale = attn_factor

            c = np.cos(theta) * mscale
            s = sin_sign * np.sin(theta) * mscale

            x0 = x[h, i]
            x1 = x[h, i + 1]
            out[h, i] = x0 * c - x1 * s
            out[h, i + 1] = x0 * s + x1 * c

    return out


# ----- 验证用: q·k 内积应只依赖相对位置差 -----


def dot_product(q: np.ndarray, k: np.ndarray) -> float:
    """对每 head 做内积, 求和返回标量 (用来观察 RoPE 的相对位置编码性质)."""
    return float(np.sum(q * k))
