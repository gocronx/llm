"""test.py —— 投机解码的正确性 + 加速效果."""
from __future__ import annotations

from speculative import (
    make_draft,
    make_target,
    naive_decode,
    speculative_decode,
)


def test_correctness_perfect_draft() -> bool:
    """draft 100% 准时, 投机解码 = 朴素解码 (输出完全一致)."""
    target = make_target(seed=1)
    perfect_draft = make_draft(target, accuracy=1.0)

    out_naive, _ = naive_decode([1, 2, 3], n_steps=20, target=target)
    out_spec, stats = speculative_decode([1, 2, 3], n_steps=20, target=target, draft=perfect_draft, lookahead=4)

    ok = out_naive == out_spec
    print(f"{'✓' if ok else '✗'} perfect draft → 输出与朴素一致")
    print(f"   stats: target_calls={stats.target_calls} (vs 朴素 {20}), accept={stats.accepted}, bonus={stats.bonus}")
    return ok


def test_correctness_bad_draft() -> bool:
    """draft 0% 准时, 投机解码也应给跟朴素一致的结果 (虽然每次都 reject)."""
    target = make_target(seed=2)
    bad_draft = make_draft(target, accuracy=0.0)

    out_naive, _ = naive_decode([1, 2], n_steps=15, target=target)
    out_spec, stats = speculative_decode([1, 2], n_steps=15, target=target, draft=bad_draft, lookahead=4)

    ok = out_naive == out_spec
    print(f"{'✓' if ok else '✗'} bad draft → 输出仍与朴素一致 (但慢)")
    print(f"   stats: target_calls={stats.target_calls}, reject={stats.rejected}")
    return ok


def test_correctness_mixed_draft() -> bool:
    """draft 70% 准, 投机解码输出必须跟朴素一字不差 (这是投机解码的核心保证: lossless)."""
    target = make_target(seed=3)
    mixed = make_draft(target, accuracy=0.7)

    out_naive, _ = naive_decode([10, 20, 30], n_steps=30, target=target)
    out_spec, stats = speculative_decode([10, 20, 30], n_steps=30, target=target, draft=mixed, lookahead=4)

    ok = out_naive == out_spec
    print(f"{'✓' if ok else '✗'} mixed draft → 输出与朴素一字不差 (lossless guarantee)")
    print(f"   stats: target_calls={stats.target_calls} (vs 朴素 30), accept={stats.accepted}, reject={stats.rejected}, bonus={stats.bonus}")
    return ok


def test_speedup_proportional_to_accuracy() -> bool:
    """draft accuracy 越高, target_calls 越少 (即加速比越高)."""
    target = make_target(seed=4)
    results = []
    for acc in [0.3, 0.5, 0.7, 0.9]:
        draft = make_draft(target, accuracy=acc)
        _, stats = speculative_decode([1], n_steps=100, target=target, draft=draft, lookahead=4)
        speedup = 100 / stats.target_calls
        results.append((acc, stats.target_calls, speedup))
        print(f"   accuracy={acc}: target_calls={stats.target_calls}, 加速={speedup:.2f}×")
    # 加速应单调增 (大概率)
    speedups = [r[2] for r in results]
    ok = speedups[0] < speedups[-1]
    print(f"{'✓' if ok else '✗'} speedup increases with draft accuracy")
    return ok


def test_margin_filter_reduces_wasted_drafts() -> bool:
    """margin filter 应在低 confidence 时早停, 减少 draft 浪费."""
    target = make_target(seed=5)
    draft = make_draft(target, accuracy=0.5)   # 50% 时 confidence 一半高一半低

    _, no_filter = speculative_decode([1], 50, target, draft, lookahead=8, margin_threshold=0.0)
    _, with_filter = speculative_decode([1], 50, target, draft, lookahead=8, margin_threshold=1.5)

    print(f"   no_filter:  draft_calls={no_filter.draft_calls}, target_calls={no_filter.target_calls}")
    print(f"   margin=1.5: draft_calls={with_filter.draft_calls}, target_calls={with_filter.target_calls}, margin_filtered={with_filter.margin_filtered}")

    ok = with_filter.margin_filtered > 0 and with_filter.draft_calls < no_filter.draft_calls
    print(f"{'✓' if ok else '✗'} margin filter reduces drafts (filtered {with_filter.margin_filtered})")
    return ok


def test_bonus_token_on_full_accept() -> bool:
    """全 accept 时应拿到 1 个 bonus token."""
    target = make_target(seed=6)
    perfect = make_draft(target, accuracy=1.0)

    _, stats = speculative_decode([1], n_steps=20, target=target, draft=perfect, lookahead=4)
    # 全 accept → 每轮 K+1 个 token, K=4 时 4 轮就能搞 20 个
    # bonus 数 ≈ rounds (假设全 accept)
    print(f"   stats: rounds={stats.rounds}, accepted={stats.accepted}, bonus={stats.bonus}")
    ok = stats.bonus > 0
    print(f"{'✓' if ok else '✗'} bonus token granted on full-accept rounds")
    return ok


def main() -> None:
    tests = [
        test_correctness_perfect_draft,
        test_correctness_bad_draft,
        test_correctness_mixed_draft,
        test_speedup_proportional_to_accuracy,
        test_margin_filter_reduces_wasted_drafts,
        test_bonus_token_on_full_accept,
    ]
    passed = sum(t() for t in tests)
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
