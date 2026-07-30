"""test.py —— Generation 主循环的停止条件 + 流式回调 + 统计."""
from __future__ import annotations

import numpy as np
from generation import KVCache, MockModel, generate


def argmax_sampler(logits: np.ndarray) -> int:
    return int(np.argmax(logits))


def test_basic_generation() -> bool:
    """基本生成: prompt + 10 token, 应得到 10 个生成 token."""
    model = MockModel(n_vocab=100, ctx_size=128)
    out, stats = generate(model, prompt=[1, 2, 3], max_tokens=10, sample_fn=argmax_sampler)
    ok = len(out) == 10 and stats.generated_tokens == 10 and stats.stop_reason == "max_tokens"
    print(f"{'✓' if ok else '✗'} basic generation: {len(out)} tokens, stop={stats.stop_reason}, "
          f"prefill={stats.prefill_ms:.2f}ms, decode={stats.decode_ms:.2f}ms")
    return ok


def test_eos_stop() -> bool:
    """sample_fn 一旦返回 EOS, 立刻停, 不再 forward."""
    # Sampler 第 5 次返回 EOS=99
    counter = {"n": 0}
    def sampler(logits):
        counter["n"] += 1
        return 99 if counter["n"] == 5 else 1
    model = MockModel(n_vocab=100)
    out, stats = generate(model, prompt=[0], max_tokens=20, sample_fn=sampler, eos_token=99)
    ok = stats.stop_reason == "eos" and out[-1] == 99 and len(out) == 5
    print(f"{'✓' if ok else '✗'} EOS stop: stopped at {len(out)} tokens, reason={stats.stop_reason}")
    return ok


def test_ctx_size_stop() -> bool:
    """ctx_size 小, prompt+gen 接近上限时停."""
    model = MockModel(n_vocab=50, ctx_size=10)
    out, stats = generate(model, prompt=[1, 2, 3], max_tokens=100, sample_fn=argmax_sampler)
    # ctx=10, prompt=3, 应能生成 ≤ 7 个 token 就触发 ctx_full
    ok = stats.stop_reason == "ctx_full" and len(out) < 10
    print(f"{'✓' if ok else '✗'} ctx_size stop: prompt=3+gen={len(out)}, ctx=10, reason={stats.stop_reason}")
    return ok


def test_emit_callback_streaming() -> bool:
    """emit_fn 每生成 1 个 token 都该被调一次 (流式)."""
    model = MockModel()
    emitted = []
    out, stats = generate(model, prompt=[1], max_tokens=8, sample_fn=argmax_sampler,
                          emit_fn=lambda t: emitted.append(t))
    ok = emitted == out and len(emitted) == 8
    print(f"{'✓' if ok else '✗'} streaming emit: {len(emitted)} callbacks == {len(out)} tokens")
    return ok


def test_reproducible_with_argmax() -> bool:
    """argmax sampler + 确定性 model → 同一 prompt 跑两次应得到相同输出."""
    model = MockModel()
    out1, _ = generate(model, [1, 2, 3], 15, argmax_sampler)
    out2, _ = generate(model, [1, 2, 3], 15, argmax_sampler)
    ok = out1 == out2
    print(f"{'✓' if ok else '✗'} reproducibility: 两次跑相同, len={len(out1)}")
    return ok


def test_kv_cache_length_tracks() -> bool:
    """KV cache len 应跟 prompt+generated 一致."""
    model = MockModel(ctx_size=64)
    cache = KVCache(64)
    model.prefill([1, 2, 3, 4], cache)
    assert cache.len == 4
    model.forward(5, 4, cache)
    assert cache.len == 5
    print(f"✓ KV cache len tracks (prefill 4 + forward 1 → len=5)")
    return True


def test_empty_prompt_rejected() -> bool:
    """空 prompt 应直接报错, 不要静默接受."""
    model = MockModel()
    try:
        generate(model, [], 5, argmax_sampler)
        print(f"✗ empty prompt not rejected")
        return False
    except ValueError:
        print(f"✓ empty prompt rejected with ValueError")
        return True


def test_prompt_too_long_rejected() -> bool:
    """prompt 超 ctx_size 时直接报错."""
    model = MockModel(ctx_size=10)
    try:
        generate(model, [1] * 20, 5, argmax_sampler)
        print(f"✗ prompt > ctx_size not rejected")
        return False
    except ValueError:
        print(f"✓ prompt > ctx_size rejected with ValueError")
        return True


def main() -> None:
    tests = [
        test_basic_generation,
        test_eos_stop,
        test_ctx_size_stop,
        test_emit_callback_streaming,
        test_reproducible_with_argmax,
        test_kv_cache_length_tracks,
        test_empty_prompt_rejected,
        test_prompt_too_long_rejected,
    ]
    passed = sum(t() for t in tests)
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
