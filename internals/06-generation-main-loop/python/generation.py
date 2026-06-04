"""generation.py —— LLM 推理 generation 主循环骨架.

抽自 ds4.c:15119 (`generate_raw_swa_cpu`). 是所有 LLM 推理引擎 (llama.cpp / vLLM / SGLang)
的核心 loop, 把 "model forward + sampling + stop condition" 串起来.

## Prefill vs Decode 的区别

```
   prompt = [t0, t1, t2, ..., t_{P-1}]    (P 个 prompt token)

   Prefill (一次):
     喂全部 P 个 token, 写 P 行 KV cache, 拿到位置 P-1 的 logits
     时间 O(P) 但矩阵乘 GPU 友好 (大矩阵), 实际很快

   Decode loop (每生成 1 个 token):
     喂 1 个新 token, 写 1 行 KV cache, 拿到下一位置的 logits
     时间 O(1) 但 GPU 利用率低 (单 token 矩阵乘), token/s 上限受制于此
```

| | Prefill | Decode |
|--|--------|--------|
| 喂入 | 整个 prompt | 1 个 token |
| KV 写入 | P 行 | 1 行 |
| GPU 占用 | 高 (大 batch) | 低 (单 token) |
| 时间 | TTFT (Time To First Token) | TPOT (Time Per Output Token) |
| 优化目标 | 不大, 用户体验"等开始" | 大, 用户体验"流畅度" |

vLLM / SGLang 等做的 continuous batching 和 chunked prefill 都是为了让 prefill 和 decode
更好地共存在一个 batch 里, 提高 GPU 利用率.

## KV cache 是什么

attention 算 softmax(Q · K^T) · V 时, 第 t 个 token 的 K, V 用到所有 t' ≤ t 的历史 token.
每次 forward 都重算所有 K, V 浪费, 所以**缓存**每个 token 在每层的 K, V, 下一轮直接拼接.

教学版用 list 模拟 (不实现真 KV cache, 但有 KVCache 类展示接口).

## 停止条件

3 个独立条件, 任一触发即停:
1. **EOS token**: 模型自己说"完事了"
2. **max_tokens**: 用户给的预算
3. **ctx_size**: 物理上下文窗口限制 (prefill+decode 不能超)

## 教学版做什么

- `MockModel` 实现 forward(token, pos) -> logits 接口
- `KVCache` 占位 (真实实现要复杂得多)
- `generate()` 主循环: prefill + decode + sampling + emit callback
- 配合 G01 的 sampling 一起用
- 统计 prefill_ms / decode_ms / tok_per_s
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


# ----- 接口定义 -----

class Model(Protocol):
    """LLM model 接口. 真实模型是个 transformer; 教学版 mock."""

    n_vocab: int
    ctx_size: int

    def forward(self, token: int, pos: int, cache: "KVCache") -> np.ndarray:
        """喂 1 个 token, 返回 (n_vocab,) logits. 这是 decode 步用的."""
        ...

    def prefill(self, tokens: list[int], cache: "KVCache") -> np.ndarray:
        """一次性喂多个 token (prompt), 返回最后一个位置的 logits.

        真实实现里 prefill 内部也会逐 layer/逐 batched-token forward, 但 GPU 上对外是 1 次 call."""
        ...


class KVCache:
    """KV cache 教学占位. 真实实现要存 (n_layer, n_head, max_ctx, head_dim) 大 tensor."""

    def __init__(self, ctx_size: int):
        self.ctx_size = ctx_size
        self.len = 0
        # 教学版只记 token sequence, 真实存 K/V tensor
        self._tokens: list[int] = []

    def append(self, token: int) -> None:
        if self.len >= self.ctx_size:
            raise RuntimeError(f"KV cache full ({self.ctx_size})")
        self._tokens.append(token)
        self.len += 1

    def reset(self) -> None:
        self._tokens.clear()
        self.len = 0


# ----- 主循环 -----

@dataclass
class GenStats:
    prompt_tokens: int = 0
    generated_tokens: int = 0
    prefill_ms: float = 0.0
    decode_ms: float = 0.0
    stop_reason: str = ""

    @property
    def tokens_per_sec(self) -> float:
        if self.decode_ms <= 0:
            return 0.0
        return self.generated_tokens / (self.decode_ms / 1000.0)


def generate(
    model: Model,
    prompt: list[int],
    max_tokens: int,
    sample_fn: Callable[[np.ndarray], int],
    eos_token: int | None = None,
    emit_fn: Callable[[int], None] | None = None,
) -> tuple[list[int], GenStats]:
    """LLM 推理主循环. 返回 (生成的 token list, 统计).

    参数:
      model: 实现 Model 接口
      prompt: prompt token id 列表
      max_tokens: 最多生成多少 token (不含 prompt)
      sample_fn: logits → token_id, 通常是 G01 的 sample()
      eos_token: 遇到这个 id 就停, None 表示不启用
      emit_fn: 流式回调, 每生成 1 个 token 立刻调一次 (UI 显示)

    主循环结构 (跟 ds4.c:15119 一致):
      1. 初始化 KV cache
      2. Prefill: 喂 prompt, 拿到第一个 logits
      3. Decode loop:
         a. sample → token
         b. emit + 检查停止 (EOS / max / ctx)
         c. forward(token, pos++) → 新 logits
      4. 返回生成 list + stats
    """
    import time

    if not prompt:
        raise ValueError("prompt must be non-empty")
    if len(prompt) > model.ctx_size:
        raise ValueError(f"prompt ({len(prompt)}) exceeds ctx_size ({model.ctx_size})")

    cache = KVCache(model.ctx_size)
    stats = GenStats(prompt_tokens=len(prompt))

    # ----- 1. Prefill -----
    t0 = time.perf_counter()
    logits = model.prefill(prompt, cache)
    stats.prefill_ms = (time.perf_counter() - t0) * 1000

    generated: list[int] = []

    # ----- 2. Decode loop -----
    t0 = time.perf_counter()
    for step in range(max_tokens):
        token = sample_fn(logits)
        if emit_fn:
            emit_fn(token)
        generated.append(token)
        stats.generated_tokens += 1

        if eos_token is not None and token == eos_token:
            stats.stop_reason = "eos"
            break

        if cache.len + 1 >= model.ctx_size:
            stats.stop_reason = "ctx_full"
            break

        if step == max_tokens - 1:
            stats.stop_reason = "max_tokens"
            break

        # 喂刚 sampled 的 token, 拿到下一位置的 logits
        logits = model.forward(token, cache.len, cache)

    stats.decode_ms = (time.perf_counter() - t0) * 1000
    if not stats.stop_reason:
        stats.stop_reason = "max_tokens"
    return generated, stats


# ----- Mock model: 帮助 demo 跑起来 -----

class MockModel:
    """Mock LLM, 用于教学. forward 用 RNG seed=hash(history) 假装是 transformer.

    给定 history → 输出确定性 logits, 这样 sample(argmax) 会输出可复现序列."""

    def __init__(self, n_vocab: int = 100, ctx_size: int = 1024):
        self.n_vocab = n_vocab
        self.ctx_size = ctx_size

    def _logits_from_seed(self, seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed & 0xFFFFFFFF)
        return rng.standard_normal(self.n_vocab).astype(np.float32) * 3

    def prefill(self, tokens: list[int], cache: KVCache) -> np.ndarray:
        for t in tokens:
            cache.append(t)
        return self._logits_from_seed(hash(tuple(tokens)))

    def forward(self, token: int, pos: int, cache: KVCache) -> np.ndarray:
        cache.append(token)
        return self._logits_from_seed(hash(tuple(cache._tokens)))
