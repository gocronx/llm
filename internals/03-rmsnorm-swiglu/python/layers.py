"""layers.py —— RMSNorm + SwiGLU. 现代 LLM 的 normalization + activation 标配.

抽自 ds4.c:2700 (rms_norm_*) 和 ds4.c:5012 (silu/swiglu). LLaMA/Mistral/Qwen/DeepSeek 都长这样.

## RMSNorm vs LayerNorm

经典 LayerNorm:
  y = (x - mean(x)) / sqrt(var(x) + eps) * gamma + beta
  → 2 个统计量 (均值 + 方差), 2 个学习参数 (gamma, beta)

RMSNorm (Root Mean Square Norm):
  y = x / sqrt(mean(x²) + eps) * gamma
  → 1 个统计量, 1 个学习参数

为什么砍掉减均值: 论文证明 (Zhang & Sennrich 2019) 重要的是 re-scaling, 不是 re-centering.
实测精度不掉, 但**快 10-50%** (省一遍遍历求均值). 现代 LLM 几乎清一色用 RMSNorm.

## SiLU + SwiGLU

SiLU (Swish): `silu(x) = x * sigmoid(x)`
  - 比 ReLU 平滑, 比 GELU 计算简单
  - 在 0 附近近似 x/2, 远离 0 近似 ReLU(x)

SwiGLU (Gated Linear Unit with SiLU):
  - 在 FFN 里把 `relu(W1·x)` 替成 `silu(gate·x) * (up·x)`
  - 多一个 `up` 投影, 但模型质量比 ReLU/GELU 显著高 (Shazeer 2020)
  - 现代 LLaMA/Mistral/Qwen 全用 SwiGLU

## 数值稳定 sigmoid

朴素 sigmoid:  `1 / (1 + exp(-x))`
  - x = -100 时, `exp(100) ≈ 2.7e43` → 溢出 inf
  - x = +100 时, `exp(-100) ≈ 0` → underflow 不致命但精度损失

数值稳定版:
  - x ≥ 0:  `1 / (1 + exp(-x))`   ← exp(-x) ∈ (0, 1], 安全
  - x <  0:  `exp(x) / (1 + exp(x))` ← exp(x) ∈ (0, 1], 安全

不显式做这个判断, fp16 训练就会崩.
"""

from __future__ import annotations

import numpy as np


def rms_norm(
    x: np.ndarray, weight: np.ndarray | None = None, eps: float = 1e-6
) -> np.ndarray:
    """RMSNorm: y = x / sqrt(mean(x²) + eps) * weight (weight=None 时无学习缩放).

    x shape (..., n), 最后一维做 normalization. weight shape (n,).

    注意 ss 用 float64 累加防大向量精度损失 (vocab 数百万维时 fp32 累加会丢精度)."""
    ss = (x.astype(np.float64) ** 2).mean(axis=-1, keepdims=True)
    scale = 1.0 / np.sqrt(ss + eps)
    out = x * scale.astype(x.dtype)
    if weight is not None:
        out = out * weight
    return out


def rms_norm_per_head(x: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """对 (n_head, head_dim) 形状的 q/k 做 per-head RMSNorm. 现代 LLM 在 Q/K 投影后会做."""
    return rms_norm(x, weight=None, eps=eps)


# ---------------- Activations ----------------


def sigmoid_stable(x: np.ndarray) -> np.ndarray:
    """数值稳定 sigmoid. x ≥ 0 用 1/(1+e^-x), x < 0 用 e^x/(1+e^x).

    vs naive `1/(1+exp(-x))`: 后者在 x ≈ -100 时 exp 溢出 inf."""
    out = np.empty_like(x, dtype=np.float64)
    pos_mask = x >= 0
    # x >= 0 分支
    e_neg = np.exp(-x[pos_mask])
    out[pos_mask] = 1.0 / (1.0 + e_neg)
    # x < 0 分支
    e_pos = np.exp(x[~pos_mask])
    out[~pos_mask] = e_pos / (1.0 + e_pos)
    return out.astype(x.dtype)


def silu(x: np.ndarray) -> np.ndarray:
    """SiLU (Swish): x * sigmoid(x). 现代 LLM 标配激活."""
    return x * sigmoid_stable(x)


def swiglu(gate: np.ndarray, up: np.ndarray) -> np.ndarray:
    """SwiGLU: silu(gate) * up. 现代 LLM FFN 的核心.

    在 transformer FFN 里, x → [Wgate · x, Wup · x] → silu(Wgate·x) * (Wup·x) → Wdown · ...
    比 ReLU(W1·x) 效果更好 (Shazeer 2020), 代价是多一个投影矩阵."""
    return silu(gate) * up


# ---------------- 对照: 经典 LayerNorm (不在现代 LLM 用, 留作对比) ----------------


def layer_norm(
    x: np.ndarray,
    weight: np.ndarray | None = None,
    bias: np.ndarray | None = None,
    eps: float = 1e-5,
) -> np.ndarray:
    """经典 LayerNorm. 教学用, 现代 LLM 已被 RMSNorm 取代."""
    mean = x.mean(axis=-1, keepdims=True)
    var = x.var(axis=-1, keepdims=True)
    out = (x - mean) / np.sqrt(var + eps)
    if weight is not None:
        out = out * weight
    if bias is not None:
        out = out + bias
    return out
