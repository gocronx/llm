"""sampling.py —— Top-K + Top-P + Min-P + Temperature 采样管道.

抽自 ds4.c 的 sample_top_p_min_p (一份 antirez 风格的 C 推理引擎). 这是当今 LLM 推理
框架里最常见的采样组合, llama.cpp / vLLM / SGLang 都长这样.

## 数学步骤

  logits ──[temperature]──> 缩放后的 logits
         ──[top_k]──> 取前 K 个 (id 排序按 logit desc)
         ──[softmax]──> probs (减最大值的数值稳定写法)
         ──[min_p]──> 砍掉相对最高概率太小的 (绝对阈值: probs[0] * min_p)
         ──[top_p]──> 累积概率到 top_p 即止
         ──[CDF sample]──> 在剩余里按概率抽一个

## 退化关系 (可作为正确性检查)

  temperature → 0    退化为 argmax (贪心)
  top_k = 1          退化为 argmax (贪心)
  top_p = 1, min_p = 0  纯 softmax 多项采样
  top_p 极小         几乎贪心 (只取最高那 1 个)
  min_p = 1          只取概率等于 max 的 (基本贪心)

## 关键工程细节 (照搬 ds4.c 的判断)

- min_p 是**相对阈值** (vs. 绝对阈值), 跟 Mistral/llama.cpp 一致: 第一个 (最高) 候选无论
  如何保留, 后续的必须 ≥ probs[0] * min_p. 这避免了"概率分布很尖, min_p 把第一个也砍掉"
- top_k 用插入排序 (不是 full sort), 因为 vocab=128k 量级时 O(V·logK) 比 O(V·logV) 快 ×10
- 数值稳定 softmax: 减 max_logit 再 exp, 避免 overflow
- 非 finite 的 logit 直接跳过 (Inf/-Inf/NaN), 不污染 sum
"""

from __future__ import annotations

import numpy as np


def sample_argmax(logits: np.ndarray) -> int:
    """温度 0 / top_k=1 时的退化路径. 不参与统计意义上的"采样"."""
    return int(np.argmax(logits))


def sample(
    logits: np.ndarray,
    temperature: float = 1.0,
    top_k: int = 50,
    top_p: float = 0.9,
    min_p: float = 0.05,
    rng: np.random.Generator | None = None,
) -> int:
    """采一个 token id. logits shape (V,). 不修改入参.

    参数:
      temperature ≤ 0  → argmax (确定性)
      top_k ≤ 0        → 不做 top_k 截 (等同于 top_k = V)
      top_p ∈ (0, 1]   → 累积概率截止点
      min_p ∈ [0, 1]   → 相对最高概率的最小阈值
    """
    rng = rng if rng is not None else np.random.default_rng()

    if temperature <= 0.0:
        return sample_argmax(logits)

    V = logits.shape[0]
    top_p = 1.0 if (top_p <= 0.0 or top_p > 1.0) else top_p
    min_p = max(0.0, min_p)
    k = top_k if (0 < top_k <= V) else V

    # --- 1. 过滤 non-finite + 取 top_k (按 logit 降序) ---
    finite = np.isfinite(logits)
    if not finite.any():
        return sample_argmax(logits)
    # 用 argpartition 找前 k 大 (O(V)), 再对这 k 个排序 (O(k log k))
    # 等价于 ds4.c 的插入排序, numpy 实现更简短
    masked = np.where(finite, logits, -np.inf)
    if k < V:
        top_idx = np.argpartition(-masked, k - 1)[:k]
    else:
        top_idx = np.arange(V)
    top_logits = masked[top_idx]
    order = np.argsort(-top_logits)  # 降序
    ids = top_idx[order]
    vals = top_logits[order]

    # --- 2. softmax (减最大值数值稳定) ---
    max_logit = vals[0]
    probs = np.exp((vals - max_logit) / temperature)
    s = probs.sum()
    if not np.isfinite(s) or s <= 0.0:
        return int(ids[0])
    probs_norm = probs / s

    # --- 3. min_p (相对阈值, 跳过第 0 个) ---
    threshold = probs_norm[0] * min_p
    # numpy 矢量化: 找第一个 i>0 且 probs_norm[i] < threshold 的位置
    below = (np.arange(len(probs_norm)) > 0) & (probs_norm < threshold)
    if below.any():
        cut_min_p = int(np.argmax(below))  # 第一个 True 的下标
    else:
        cut_min_p = len(probs_norm)

    # --- 4. top_p (累积概率 ≥ top_p 即止) ---
    cum = np.cumsum(probs_norm[:cut_min_p])
    # 找第一个 cum[i] ≥ top_p 的位置, 含本位
    hit = cum >= top_p
    if hit.any():
        cut_top_p = int(np.argmax(hit)) + 1
    else:
        cut_top_p = cut_min_p

    n = min(cut_min_p, cut_top_p)
    if n <= 0:
        return int(ids[0])

    # --- 5. CDF 采样 ---
    filtered = probs[:n]  # 用未归一化的 probs, 跟 ds4.c 一致
    r = rng.random() * filtered.sum()
    cum_filtered = np.cumsum(filtered)
    pick = int(np.searchsorted(cum_filtered, r, side="right"))
    pick = min(pick, n - 1)
    return int(ids[pick])


# --- 给学习者对照用的"教科书 softmax" ---
def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """纯 softmax, 不做任何过滤. 用来跟 sample() 的退化行为对照."""
    if temperature <= 0:
        out = np.zeros_like(logits, dtype=np.float64)
        out[int(np.argmax(logits))] = 1.0
        return out
    x = (logits - np.max(logits)) / temperature
    e = np.exp(x)
    return e / e.sum()
