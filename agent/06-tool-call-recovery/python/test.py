"""test.py —— 4 类错误恢复的检测 + 合成 summary 行为."""

from __future__ import annotations

import json

from react_loop import parse_inline_tool_calls, run_robust_react
from recovery import RecoveryConfig, ToolCallRecovery


def test_detect_empty_response() -> bool:
    r = ToolCallRecovery()
    assert r.is_empty_response("", None)  # 完全空
    assert r.is_empty_response(None, None)  # None
    assert r.is_empty_response("ok", None)  # 短于 10
    assert not r.is_empty_response("This is a real reply.", None)  # 正常
    assert not r.is_empty_response("", [{"id": "c1"}])  # 有 tool_calls
    print("✓ detect_empty_response 4 个 case 都对")
    return True


def test_detect_repeated_tool_call() -> bool:
    """连续 3 次相同 tool_call → 检测到."""
    r = ToolCallRecovery(RecoveryConfig(max_repeated_tool_calls=3))
    same_call = {
        "id": "x",
        "function": {"name": "web_search", "arguments": '{"q":"x"}'},
    }
    messages = []
    for i in range(3):
        messages.append({"role": "assistant", "tool_calls": [same_call]})
        messages.append(
            {
                "role": "tool",
                "tool_call_id": "x",
                "name": "web_search",
                "content": f"result {i}",
            }
        )

    detected, name = r.detect_repeated_tool_call(messages)
    ok = detected and name == "web_search"
    print(
        f"{'✓' if ok else '✗'} 连续 3 次相同 tool_call → detected={detected}, name={name}"
    )
    return ok


def test_no_false_positive_on_different_args() -> bool:
    """同 tool 不同 args → 不该检测为死循环."""
    r = ToolCallRecovery(RecoveryConfig(max_repeated_tool_calls=3))
    msgs = []
    for q in ["手机", "电脑", "键盘"]:
        msgs.append(
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "x",
                        "function": {
                            "name": "web_search",
                            "arguments": f'{{"q":"{q}"}}',
                        },
                    }
                ],
            }
        )
        msgs.append({"role": "tool", "tool_call_id": "x", "content": "..."})
    detected, _ = r.detect_repeated_tool_call(msgs)
    ok = not detected
    print(f"{'✓' if ok else '✗'} 同 tool 不同 args 不误判 (detected={detected})")
    return ok


def test_synthesize_summary_with_valid_results() -> bool:
    r = ToolCallRecovery()
    messages = [
        {"role": "user", "content": "查天气"},
        {"role": "tool", "name": "get_weather", "content": '{"city":"北京","temp":15}'},
        {"role": "tool", "name": "get_weather", "content": '{"city":"上海","temp":20}'},
    ]
    summary = r.synthesize_summary_from_tools(messages)
    ok = "Based on" in summary and "get_weather" in summary
    print(f"  summary: {summary[:120]}...")
    print(f"{'✓' if ok else '✗'} synthesize summary from 2 valid tool results")
    return ok


def test_synthesize_with_only_errors() -> bool:
    """只有 error 没有 valid result, 返回 sorry 文案."""
    r = ToolCallRecovery()
    messages = [
        {"role": "tool", "name": "search", "content": json.dumps({"error": "timeout"})},
        {
            "role": "tool",
            "name": "search",
            "content": json.dumps({"error": "ratelimit"}),
        },
    ]
    summary = r.synthesize_summary_from_tools(messages)
    ok = "errors" in summary.lower() and (
        "timeout" in summary or "ratelimit" in summary
    )
    print(f"  summary: {summary[:120]}")
    print(f"{'✓' if ok else '✗'} summary with only errors mentions error context")
    return ok


def test_recover_empty_response_increments_stats() -> bool:
    r = ToolCallRecovery()
    msgs = [{"role": "tool", "name": "search", "content": "data"}]
    summary = r.recover_empty_response(msgs)
    ok = r.stats.empty_response_recoveries == 1 and "search" in summary
    print(
        f"{'✓' if ok else '✗'} recover_empty_response: stats={r.stats.empty_response_recoveries}"
    )
    return ok


def test_recover_infinite_loop_returns_system_msg() -> bool:
    r = ToolCallRecovery()
    msg = r.recover_infinite_loop()
    ok = (
        msg["role"] == "system"
        and "STOP" in msg["content"]
        and r.stats.infinite_loop_breaks == 1
    )
    print(f"{'✓' if ok else '✗'} recover_infinite_loop returns system stop message")
    return ok


def test_wrap_tool_error() -> bool:
    r = ToolCallRecovery()
    err = r.wrap_tool_error("read_file", FileNotFoundError("no such file"))
    parsed = json.loads(err)
    ok = (
        "error" in parsed
        and "FileNotFoundError" in parsed["error"]
        and parsed["tool"] == "read_file"
        and r.stats.tool_errors_fed_back == 1
    )
    print(f"{'✓' if ok else '✗'} wrap_tool_error: {err[:80]}")
    return ok


def test_handle_unknown_tool() -> bool:
    r = ToolCallRecovery()
    result = r.handle_unknown_tool("super_search_v2", ["web_search", "read_file"])
    parsed = json.loads(result)
    ok = (
        "unknown tool" in parsed["error"]
        and "web_search" in parsed["available_tools"]
        and r.stats.unknown_tool_errors == 1
    )
    print(f"{'✓' if ok else '✗'} handle_unknown_tool returns hint")
    return ok


def test_should_force_summary() -> bool:
    """连续 8 个 tool 没 content 进展 → 强制总结."""
    r = ToolCallRecovery(RecoveryConfig(force_summary_after_n_tools=8))
    msgs = [{"role": "user", "content": "task"}]
    for i in range(10):
        msgs.append(
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": str(i), "function": {"name": "t", "arguments": ""}}
                ],
            }
        )
        msgs.append({"role": "tool", "tool_call_id": str(i), "content": f"r{i}"})
    ok = r.should_force_summary(msgs)
    print(f"{'✓' if ok else '✗'} should_force_summary after 10 consecutive tool calls")
    return ok


def test_count_recent_tool_calls() -> bool:
    """count 检测末尾连续 tool 数量, 遇到非空 content 中断."""
    r = ToolCallRecovery()
    msgs = [
        {"role": "user", "content": "x"},
        {"role": "assistant", "content": "I'll search..."},  # 实质 content
        {"role": "tool", "content": "r1"},
        {"role": "tool", "content": "r2"},
        {"role": "tool", "content": "r3"},
    ]
    n = r.count_recent_tool_calls(msgs)
    ok = n == 3
    print(f"{'✓' if ok else '✗'} count_recent_tool_calls: {n} (expected 3)")
    return ok


def test_inline_tool_parser_preserves_invalid_source() -> bool:
    """合法调用被提取，非法调用继续留给模型自我修正。"""
    valid = '<tool_call>{"name":"search","arguments":{"q":"x"}}</tool_call>'
    calls, cleaned = parse_inline_tool_calls(f"before {valid} after")
    malformed = '<tool_call>{"name": missing quote}</tool_call>'
    invalid_calls, invalid_content = parse_inline_tool_calls(malformed)
    return (
        calls[0]["function"]["name"] == "search"
        and cleaned == "before  after"
        and invalid_calls == []
        and invalid_content == malformed
    )


def test_react_loop_feeds_unknown_tool_back() -> bool:
    """未知工具转换为 tool result，下一轮仍能得到最终答案。"""
    responses = iter(
        [
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "x",
                        "function": {"name": "missing", "arguments": "{}"},
                    }
                ],
            },
            {"content": "recovered answer", "tool_calls": []},
        ]
    )
    recovery = ToolCallRecovery()
    answer, messages = run_robust_react(
        [{"role": "user", "content": "task"}],
        lambda _messages: next(responses),
        recovery,
        {},
    )
    return (
        answer == "recovered answer"
        and recovery.stats.unknown_tool_errors == 1
        and any(message.get("role") == "tool" for message in messages)
    )


def main() -> None:
    tests = [
        test_detect_empty_response,
        test_detect_repeated_tool_call,
        test_no_false_positive_on_different_args,
        test_synthesize_summary_with_valid_results,
        test_synthesize_with_only_errors,
        test_recover_empty_response_increments_stats,
        test_recover_infinite_loop_returns_system_msg,
        test_wrap_tool_error,
        test_handle_unknown_tool,
        test_should_force_summary,
        test_count_recent_tool_calls,
        test_inline_tool_parser_preserves_invalid_source,
        test_react_loop_feeds_unknown_tool_back,
    ]
    passed = sum(t() for t in tests)
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
