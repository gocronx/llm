"""quant.py —— FP8 (E4M3FN) 量化反量化 + Q8 per-block 量化对照.

抽自 ds4.c:1590 (dsv4_e4m3fn_value), 1605 (dequant), 1660 (block 量化), 1700 (Q8_K).

## 为什么要量化

LLM 参数和 activation 都是 fp16/fp32, 存储和计算都很贵:
- LLaMA-70B: 70B × 2 bytes = 140 GB (fp16) → 一张 A100 80G 装不下
- KV cache 跟序列长度成正比, 长 context 直接爆显存

把数值压成 8 bits, 显存 / 带宽 / 算力都 ×2 (或 fp16→4bit 是 ×4). 关键问题: **怎么压而不丢精度**?

## 两种 8-bit 量化思路

### FP8 E4M3FN (硬件支持的浮点 8-bit)

8 bit = 1 sign + 4 exp + 3 mantissa. 不带 NaN/Inf 的子集 (FN = Finite, No-NaN).

| 字段 | bits | 作用 |
|------|------|------|
| sign | 1 | 正负 |
| exp  | 4 | 数量级 (bias=7) |
| mant | 3 | 精度 (1.xxx 的 3 位小数) |

可表示值范围: [-448, +448], 共 254 个 representable values.

**优点**: 像 fp16 一样自带 dynamic range (用 exp 表示数量级), 不需要外部 scale.
**缺点**: 表的非线性, 二分搜索找最近 representable 慢; 大数值精度低 (mant 只 3 bits).

H100/B200 都原生支持 FP8 计算 (Tensor Core), 是 2024+ LLM 推理标配.

### Q8 per-block (整数 8-bit + 共享 scale)

把 N 个 fp32 分一个 block (典型 N=32 或 64), 计算 block 内 amax = max(|x_i|), 算 `scale = amax/127`,
存 int8 值 `q_i = round(x_i / scale)`, 再存 scale 共享.

每 block 总开销 = N×1 byte (int8) + 1×4 byte (scale fp32) = 1.125 byte/value (block=32 时).

**优点**: 算术简单 (整数乘加), 在没有 FP8 硬件的卡上比 FP8 软件实现快.
**缺点**: 显式 per-block scale 存储, KV cache 实现复杂.

## ds4.c 用谁

- 模型权重: IQ2_XXS / Q2_K / Q4_K (更激进, 这里没演示)
- KV cache 的 NoPE 部分: **FP8 E4M3FN**
- Activation: **Q8_K** (跟 GGUF Q2_K 等做 matmul)

教学版同时实现 FP8 和 Q8, 你能看到两套不同的"per-block dynamic scaling"思路.
"""
from __future__ import annotations

import numpy as np

FP8_MAX = 448.0          # E4M3FN 可表示的最大正值
FP8_N_CODES = 127        # 索引范围 [0, 126], i=127 留给特殊 (这里跳过)
Q8_BLOCK_SIZE = 32       # Q8 每个 block 内的元素数


# ----- FP8 E4M3FN -----

def fp8_e4m3_value(i: int) -> float:
    """FP8 E4M3FN 索引 i ∈ [0, 126] → 对应正值. 复刻 ds4.c:dsv4_e4m3fn_value_cpu."""
    exp = (i >> 3) & 0xf
    mant = i & 0x7
    if exp == 0:
        # subnormal: mant * 2^-9
        return mant * 0.001953125
    # normal: (1 + mant/8) * 2^(exp-7)
    exp_scale = 2.0 ** (exp - 7)
    return (1.0 + mant * 0.125) * exp_scale


def build_fp8_table() -> np.ndarray:
    """预计算 127 个 FP8 正值 (升序). 二分搜索时用."""
    return np.array([fp8_e4m3_value(i) for i in range(FP8_N_CODES)], dtype=np.float32)


_FP8_TABLE = build_fp8_table()


def fp8_e4m3_quantize_one(x: float) -> float:
    """单个 fp32 → 最近的 FP8 representable value (含符号)."""
    sign = -1.0 if x < 0 else 1.0
    ax = min(abs(x), FP8_MAX)
    # 二分找最大 i 使 _FP8_TABLE[i] <= ax
    idx = int(np.searchsorted(_FP8_TABLE, ax, side="right")) - 1
    idx = max(0, min(idx, FP8_N_CODES - 1))
    # 跟右邻居比, 谁更近选谁 (round-to-nearest-even)
    if idx < FP8_N_CODES - 1:
        a = _FP8_TABLE[idx]
        b = _FP8_TABLE[idx + 1]
        if abs(ax - b) < abs(ax - a):
            idx += 1
        elif abs(ax - b) == abs(ax - a) and idx % 2 == 1:  # tie → 偶数索引
            idx += 1
    return sign * _FP8_TABLE[idx]


def fp8_e4m3_quantize(x: np.ndarray) -> np.ndarray:
    """向量化版本. 用 searchsorted O(log127) 比 C 版二分快."""
    sign = np.sign(x)
    ax = np.minimum(np.abs(x), FP8_MAX)
    idx = np.searchsorted(_FP8_TABLE, ax, side="right") - 1
    idx = np.clip(idx, 0, FP8_N_CODES - 1)
    # 跟右邻居比看谁近
    cur_v = _FP8_TABLE[idx]
    next_idx = np.minimum(idx + 1, FP8_N_CODES - 1)
    next_v = _FP8_TABLE[next_idx]
    use_next = np.abs(ax - next_v) < np.abs(ax - cur_v)
    final_idx = np.where(use_next, next_idx, idx)
    return (sign * _FP8_TABLE[final_idx]).astype(x.dtype)


def fp8_quantize_block_inplace(x: np.ndarray, block_size: int = 64) -> np.ndarray:
    """对 x 分 block 做 dynamic scale + FP8 round-trip.

    每个 block 算 amax, scale = 2^ceil(log2(amax/448)) (power-of-2, 硬件友好).
    然后 x/scale 截到 [-448,+448], FP8 quantize, 再乘回 scale.

    返回反量化后的 fp32 (跟原 x 同形状). 这是 KV cache 量化的标准做法."""
    x = x.copy().astype(np.float32)
    flat = x.reshape(-1)
    n = len(flat)
    for start in range(0, n, block_size):
        end = min(start + block_size, n)
        block = flat[start:end]
        amax = max(np.abs(block).max(), 1e-4)
        # scale = 2 ^ ceil(log2(amax/448))
        # 用 power-of-2 scale, 这样 x/scale 是简单的指数移位 (硬件友好)
        log2_scale = np.ceil(np.log2(amax / FP8_MAX))
        scale = 2.0 ** log2_scale
        scaled = np.clip(block / scale, -FP8_MAX, FP8_MAX)
        flat[start:end] = fp8_e4m3_quantize(scaled) * scale
    return flat.reshape(x.shape)


# ----- Q8 per-block (int8 + scale) -----

def q8_quantize_block(x: np.ndarray, block_size: int = Q8_BLOCK_SIZE) -> tuple[np.ndarray, np.ndarray]:
    """对 x 分 block 量化成 int8 + per-block scale (fp32).

    返回 (int8_codes, scales). int8_codes shape (n,), scales shape (n_blocks,).
    """
    flat = x.flatten().astype(np.float32)
    n = len(flat)
    n_blocks = (n + block_size - 1) // block_size

    codes = np.zeros(n, dtype=np.int8)
    scales = np.zeros(n_blocks, dtype=np.float32)

    for b in range(n_blocks):
        s, e = b * block_size, min((b + 1) * block_size, n)
        block = flat[s:e]
        amax = np.abs(block).max()
        if amax == 0.0:
            scales[b] = 0.0
            continue
        # 用 127 而不是 128 防 negative overflow (-128 是合法 int8 但难用)
        scale = amax / 127.0
        scales[b] = scale
        codes[s:e] = np.clip(np.round(block / scale), -127, 127).astype(np.int8)

    return codes, scales


def q8_dequantize(codes: np.ndarray, scales: np.ndarray, block_size: int = Q8_BLOCK_SIZE) -> np.ndarray:
    """int8 codes + scales → fp32. 反量化是简单乘法."""
    out = np.zeros(len(codes), dtype=np.float32)
    n_blocks = len(scales)
    for b in range(n_blocks):
        s, e = b * block_size, min((b + 1) * block_size, len(codes))
        out[s:e] = codes[s:e].astype(np.float32) * scales[b]
    return out


def q8_roundtrip(x: np.ndarray, block_size: int = Q8_BLOCK_SIZE) -> np.ndarray:
    codes, scales = q8_quantize_block(x, block_size)
    return q8_dequantize(codes, scales, block_size).reshape(x.shape)
