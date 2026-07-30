"""speculative.py —— 投机解码 (Speculative Decoding / MTP).

抽自 ds4.c:17575 (`ds4_session_eval_speculative_argmax`), 简化 GPU 耦合, 保留核心思想.

## 为什么需要投机解码

LLM 自回归解码 = 每生成 1 个 token 跑 1 次 full forward. 70B 模型一次 forward 几十 ms,
所以 token/s = 1000/forward_ms ≈ 30 token/s 上限 (一张 H100). 用户体验差.

但每次 forward 时, 模型其实**消化了整个 prompt + history**, 计算只为产 1 个 token. 浪费.

## 核心思想 (Leviathan et al. 2023)

引入两个模型:
- **Target 模型** (大模型, 慢但准): 最终输出权威
- **Draft 模型** (小模型 / target 自带的轻量 head, 快但偶尔错): 预测后续 K 个 token

每轮:
1. **Draft** 顺序预测 K 个 token (K 次小 forward, 快)
2. **Target 一次性 forward** 这 K 个位置 (1 次大 forward, 但 batch=K, 几乎跟 1 个 token 同时间)
3. **Verify**: 比对 target 的 argmax 跟 draft 是否一致
   - 一致 → accept
   - 第一个 mismatch → 用 target 的 token 替换该位置, 后面 draft 全弃
4. **Bonus**: 全 accept 时, target 还顺手算好了第 K+1 个位置的 logits, 免费送 1 个 token

理论加速: K+1 倍 (如果 draft 全对); 平均加速 = (1 + accept_rate * K).

## DeepSeek V4 的 margin 改进

朴素投机: draft 模型 argmax 直接当 draft.
DS4 改进 (margin filter): draft 的 top1 - top2 logit 差 < threshold 时, 不要 draft (模型自己不确定).
  → 避免低 confidence 的 draft 拖累 verify (反正 target 也大概率不会同意)

ds4.c:17629 处 `mtp_margin_threshold` 就是干这事的.

## 教学版简化

- Target / Draft 用 mock 函数 (确定性 RNG + 故意制造 70% draft 准确率)
- 不实现 batched verify (真实 GPU 是 1 次 forward 算 K 个 logits, 教学版串行调用计数等价)
- 不实现 KV cache 回滚 (真实 GPU 必须把 reject 部分的 KV state 复原)
- 保留: 主循环 + accept/reject 决策 + margin filter + bonus token
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


@dataclass
class DecodeStats:
    """投机解码的统计."""

    target_calls: int = 0  # target 模型 forward 次数 (理论时间成本主项)
    draft_calls: int = 0  # draft 模型 forward 次数 (便宜)
    accepted: int = 0  # accept 的 draft token 数
    rejected: int = 0  # reject 的 draft token 数
    bonus: int = 0  # 全 accept 时拿到的免费 bonus token 数
    margin_filtered: int = 0  # 因 margin 太低被丢弃的 draft 数
    rounds: int = 0  # 投机循环轮次


def naive_decode(
    prefix: list[int],
    n_steps: int,
    target: Callable[[list[int]], int],
) -> tuple[list[int], DecodeStats]:
    """朴素自回归: 每生成 1 个 token = 1 次 target forward."""
    history = list(prefix)
    stats = DecodeStats()
    for _ in range(n_steps):
        tok = target(history)
        stats.target_calls += 1
        history.append(tok)
    return history[len(prefix) :], stats


def speculative_decode(
    prefix: list[int],
    n_steps: int,
    target: Callable[[list[int]], int],
    draft: Callable[[list[int]], tuple[int, float]],
    lookahead: int = 4,
    margin_threshold: float = 0.0,
) -> tuple[list[int], DecodeStats]:
    """投机解码主循环.

    参数:
      target: target_model(history) → next_token (argmax)
      draft: draft_model(history) → (next_token, confidence_margin)
      lookahead: K, 一轮 draft 多少个
      margin_threshold: draft 的 top1-top2 margin < 这个就停止本轮 drafting (DS4 的 margin filter)

    返回: (生成的 n_steps 个 token, 统计)
    """
    history = list(prefix)
    stats = DecodeStats()

    while len(history) - len(prefix) < n_steps:
        stats.rounds += 1

        # ----- 1. Draft K 个 token -----
        drafts: list[int] = []
        margins: list[float] = []
        for k in range(lookahead):
            tok, margin = draft(history + drafts)
            stats.draft_calls += 1
            # margin filter: 第 0 个 draft 永远要 (没参考), 后续低 confidence 不要
            if k > 0 and margin < margin_threshold:
                stats.margin_filtered += 1
                break
            drafts.append(tok)
            margins.append(margin)

        if not drafts:
            break

        # ----- 2. Target verify -----
        # 计数模型: 真实 GPU 上这是 1 次 batched forward 算 K 个位置.
        # 教学版串行调 target K 次 (mock 一致性), 但 stats.target_calls 按"轮"算 (+=1),
        # 这样 stats 真实反映理论加速比.
        stats.target_calls += 1
        n_accept = 0
        replacement: int | None = None
        for i in range(len(drafts)):
            tt = target(history + drafts[:i])
            if tt == drafts[i]:
                n_accept += 1
            else:
                replacement = tt
                break

        # ----- 3. Apply: accepted drafts + replacement (或 bonus) -----
        history.extend(drafts[:n_accept])
        stats.accepted += n_accept

        if replacement is None:
            # 全 accept: bonus token 免费 (target 已经算好了 K+1 位置)
            history.extend(drafts[n_accept:])  # n_accept == len(drafts), 已经 extend 过
            extra = target(history)
            stats.target_calls += 1
            history.append(extra)
            stats.bonus += 1
        else:
            history.append(replacement)
            stats.rejected += len(drafts) - n_accept

        # 若超过 n_steps, 截断
        if len(history) - len(prefix) > n_steps:
            history = history[: len(prefix) + n_steps]

    return history[len(prefix) :], stats


# ----- Mock 模型: 用确定性 RNG 构造可重复的实验 -----


def make_target(seed: int = 0, vocab: int = 100) -> Callable[[list[int]], int]:
    """Target 模型: 给定 history 返回"标准答案"的下一个 token. 确定性."""

    def target(history: list[int]) -> int:
        h = hash(tuple(history)) ^ seed
        rng = np.random.default_rng(h & 0xFFFFFFFF)
        return int(rng.integers(0, vocab))

    return target


def make_draft(
    target: Callable[[list[int]], int],
    accuracy: float = 0.7,
    seed: int = 42,
    vocab: int = 100,
) -> Callable[[list[int]], tuple[int, float]]:
    """Draft 模型: 以 accuracy 概率跟 target 一致 (产生 margin 高); 否则瞎猜 (margin 低)."""

    def draft(history: list[int]) -> tuple[int, float]:
        h = (hash(tuple(history)) ^ seed) & 0xFFFFFFFF
        rng = np.random.default_rng(h)
        target_tok = target(history)
        if rng.random() < accuracy:
            # draft 跟 target 一致, high margin
            margin = float(rng.uniform(2.0, 5.0))
            return target_tok, margin
        else:
            # 错的 draft, low margin
            wrong = int(rng.integers(0, vocab))
            while wrong == target_tok:
                wrong = (wrong + 1) % vocab
            margin = float(rng.uniform(0.0, 1.0))
            return wrong, margin

    return draft
