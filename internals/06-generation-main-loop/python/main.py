"""main.py —— demo: 跟 G01 sampling + G06 generation 联动. 模拟一次完整推理.

加 emit 回调演示流式输出 (像 ChatGPT 那样一个一个 token 蹦出来)."""

from __future__ import annotations

import sys
import time

import numpy as np
from generation import MockModel, generate


def make_top_k_sampler(temperature: float = 0.8, top_k: int = 10):
    """简化版 G01 sampling, 内嵌进 demo (避免跨目录 import)."""
    rng = np.random.default_rng(2025)

    def sample(logits: np.ndarray) -> int:
        if temperature <= 0:
            return int(np.argmax(logits))
        # top_k 过滤
        top_idx = np.argpartition(-logits, top_k - 1)[:top_k]
        sub = logits[top_idx]
        # softmax (减最大值稳定)
        e = np.exp((sub - sub.max()) / temperature)
        probs = e / e.sum()
        pick = int(rng.choice(len(probs), p=probs))
        return int(top_idx[pick])

    return sample


def stream_emit(token: int) -> None:
    """流式打印: 每生成 1 个 token 就 print 出来 (模拟 ChatGPT 体验)."""
    sys.stdout.write(f" t{token}")
    sys.stdout.flush()
    time.sleep(0.05)  # 模拟 LLM 速度 (20 token/s)


def main() -> None:
    model = MockModel(n_vocab=200, ctx_size=512)
    prompt = [1, 2, 3, 4, 5]
    sampler = make_top_k_sampler(temperature=0.8, top_k=10)

    print(f">>> 推理开始, prompt={prompt}")
    print(f"   (词表 {model.n_vocab}, ctx {model.ctx_size})")
    print("   生成中 (流式):")
    print("  ", end="")

    out, stats = generate(
        model, prompt=prompt, max_tokens=20, sample_fn=sampler, emit_fn=stream_emit
    )

    print(f"\n\n>>> 完成. 输出 {len(out)} token, 停止原因: {stats.stop_reason}")
    print(
        f"   Prefill: {stats.prefill_ms:.2f} ms ({stats.prompt_tokens} prompt tokens)"
    )
    print(f"   Decode:  {stats.decode_ms:.2f} ms ({stats.generated_tokens} generated)")
    print(f"   实际 token/s: {stats.tokens_per_sec:.1f} (因 demo 加了 sleep)")
    print()

    # 演示停止条件: EOS
    print(">>> 演示 EOS 停止")

    def eos_after_5(logits):
        eos_after_5.count = getattr(eos_after_5, "count", 0) + 1
        return 999 if eos_after_5.count >= 5 else int(np.argmax(logits))

    model2 = MockModel(n_vocab=1000)
    out, stats = generate(model2, [1], 100, eos_after_5, eos_token=999)
    print(f"   生成 {len(out)} token 后遇 EOS=999, stop_reason={stats.stop_reason}")

    # 演示停止条件: ctx full
    print("\n>>> 演示 ctx_size 上限")
    model_small = MockModel(n_vocab=50, ctx_size=20)
    out, stats = generate(model_small, [1, 2, 3], 100, lambda l: 1)
    print(
        f"   ctx_size=20, prompt=3, 实际生成 {len(out)} token, stop_reason={stats.stop_reason}"
    )


if __name__ == "__main__":
    main()
