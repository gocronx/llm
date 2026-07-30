"""test.py —— LLMCompactor 的切片逻辑 + 失败 fallback + cooldown."""

from __future__ import annotations

from compressor import CompactConfig, LLMCompactor


# Mock LLM: 把它收到的 prompt 简单变换返回 (确定性)
def mock_llm_summarizer(prompt: str, max_tokens: int) -> str:
    return f"## Active Task\n[mock summary of {prompt.count('[')} entries]\n## Goal\n[mock goal]\n[...]"


def mock_llm_fails(prompt: str, max_tokens: int) -> str:
    raise RuntimeError("simulated LLM failure")


def mock_llm_empty(prompt: str, max_tokens: int) -> str:
    return ""


def make_messages(n_turns: int) -> list[dict]:
    """造 n_turns 轮 (user, assistant) 对话. 每轮内容用 'x' 填充模拟长 content."""
    msgs = [{"role": "system", "content": "You are helpful"}]
    msgs.append({"role": "user", "content": "Task: refactor the auth module"})
    for i in range(n_turns):
        msgs.append({"role": "assistant", "content": f"step {i}: " + "x" * 200})
        msgs.append({"role": "user", "content": f"feedback {i}: " + "y" * 200})
    return msgs


def test_should_compact_threshold() -> bool:
    """msgs 短时不触发, 长时触发."""
    c = LLMCompactor(mock_llm_summarizer, CompactConfig(threshold_tokens=1000))
    short = make_messages(2)
    long = make_messages(30)
    print(
        f"   short ({len(short)} msgs) tokens ≈ {c._estimate(short)}, should_compact={c.should_compact(short)}"
    )
    print(
        f"   long ({len(long)} msgs) tokens ≈ {c._estimate(long)}, should_compact={c.should_compact(long)}"
    )
    ok = not c.should_compact(short) and c.should_compact(long)
    print(f"{'✓' if ok else '✗'} should_compact threshold gating")
    return ok


def test_compact_preserves_system_and_first_user() -> bool:
    """压缩后, 第 0 条仍是 system, 第 1 条仍是 first_user (任务定义)."""
    c = LLMCompactor(
        mock_llm_summarizer, CompactConfig(threshold_tokens=500, keep_recent_turns=2)
    )
    msgs = make_messages(15)
    result = c.compact(msgs)
    assert result.compacted, f"compact failed: {result.failure_reason}"
    assert result.new_messages[0]["role"] == "system"
    assert result.new_messages[1]["role"] == "user"
    assert "refactor the auth module" in result.new_messages[1]["content"]
    print(
        f"✓ system + first_user 保留 (new_messages len={len(result.new_messages)}, summarized {result.n_turns_summarized} msgs)"
    )
    return True


def test_compact_keeps_recent_turns() -> bool:
    """压缩后, 最末 keep_recent_turns*2 条原文还在."""
    c = LLMCompactor(
        mock_llm_summarizer, CompactConfig(threshold_tokens=500, keep_recent_turns=3)
    )
    msgs = make_messages(15)
    last_3_turns_content = [m["content"] for m in msgs[-6:]]  # 6 = 3 turns * 2
    result = c.compact(msgs)
    new_tail = [m.get("content", "") for m in result.new_messages[-6:]]
    ok = new_tail == last_3_turns_content
    print(f"{'✓' if ok else '✗'} 末尾 {len(last_3_turns_content)} 条原文保留")
    return ok


def test_compact_replaces_middle_with_summary() -> bool:
    """压缩后中间区域 (1 个 system summary 消息) 替换了一批 turns."""
    c = LLMCompactor(
        mock_llm_summarizer, CompactConfig(threshold_tokens=500, keep_recent_turns=2)
    )
    msgs = make_messages(15)
    result = c.compact(msgs)
    # new_messages: [system] + [first_user] + [summary system] + [recent 4 turns]
    # = 1 + 1 + 1 + 4 = 7
    summary_msg = result.new_messages[2]
    assert summary_msg["role"] == "system"
    assert "[Conversation summary" in summary_msg["content"]
    assert "Active Task" in summary_msg["content"]  # mock LLM 返回的 summary 含此字段
    print(
        f"✓ middle 被 summary 替换 ({result.n_turns_summarized} 条 → 1 个 system summary)"
    )
    return True


def test_llm_failure_enters_cooldown() -> bool:
    """LLM 总结失败 → 进入 cooldown, 下次直接拒."""
    c = LLMCompactor(
        mock_llm_fails, CompactConfig(threshold_tokens=500, cooldown_seconds=5.0)
    )
    msgs = make_messages(15)
    r1 = c.compact(msgs)
    assert not r1.compacted and "failed" in (r1.failure_reason or "")

    # 立即再 compact 一次, 应该被 cooldown 拒
    r2 = c.compact(msgs)
    ok = not r2.compacted and "cooldown" in (r2.failure_reason or "")
    print(
        f"{'✓' if ok else '✗'} cooldown after failure: r1={r1.failure_reason}, r2={r2.failure_reason}"
    )
    return ok


def test_empty_llm_response_also_cooldowns() -> bool:
    """LLM 返回空字符串视为失败, 进 cooldown."""
    c = LLMCompactor(
        mock_llm_empty, CompactConfig(threshold_tokens=500, cooldown_seconds=5.0)
    )
    msgs = make_messages(15)
    r = c.compact(msgs)
    ok = not r.compacted and "empty" in (r.failure_reason or "")
    print(f"{'✓' if ok else '✗'} empty LLM response detected: {r.failure_reason}")
    return ok


def test_not_enough_turns() -> bool:
    """msgs 太短 (≤ keep_recent_turns+1), 不该尝试压缩."""
    c = LLMCompactor(
        mock_llm_summarizer, CompactConfig(threshold_tokens=10, keep_recent_turns=10)
    )
    msgs = make_messages(2)
    r = c.compact(msgs)
    ok = not r.compacted and "not enough turns" in (r.failure_reason or "")
    print(f"{'✓' if ok else '✗'} skip compact when msgs too short")
    return ok


def test_focus_topic_in_prompt() -> bool:
    """传 focus_topic 时, LLM prompt 应包含这个字符串."""
    received_prompt = {"p": ""}

    def capture_llm(prompt: str, max_tokens: int) -> str:
        received_prompt["p"] = prompt
        return "## Active Task\n[focused]"

    c = LLMCompactor(
        capture_llm, CompactConfig(threshold_tokens=500, focus_topic="refactor auth")
    )
    msgs = make_messages(15)
    c.compact(msgs)
    ok = "refactor auth" in received_prompt["p"]
    print(f"{'✓' if ok else '✗'} focus_topic injected into prompt")
    return ok


def test_source_history_is_not_duplicated_in_prompt() -> bool:
    """压缩源历史只能发送一次，避免重复消耗输入 token。"""
    received: list[str] = []

    def capture_llm(prompt: str, max_tokens: int) -> str:
        received.append(prompt)
        return "## Active Task\nsummary"

    marker = "UNIQUE_OLD_HISTORY_MARKER"
    c = LLMCompactor(
        capture_llm,
        CompactConfig(threshold_tokens=0, keep_recent_turns=1),
    )
    result = c.compact(
        [
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": marker},
            {"role": "user", "content": "recent"},
            {"role": "assistant", "content": "answer"},
        ]
    )
    return result.compacted and received[0].count(marker) == 1


def main() -> None:
    tests = [
        test_should_compact_threshold,
        test_compact_preserves_system_and_first_user,
        test_compact_keeps_recent_turns,
        test_compact_replaces_middle_with_summary,
        test_llm_failure_enters_cooldown,
        test_empty_llm_response_also_cooldowns,
        test_not_enough_turns,
        test_focus_topic_in_prompt,
        test_source_history_is_not_duplicated_in_prompt,
    ]
    passed = sum(t() for t in tests)
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
