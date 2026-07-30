"""不调用真实 LLM 的 LangGraph 恢复测试。"""
from __future__ import annotations

from graph import LoopGuardConfig, build_graph, initial_state
from planner import RuleBasedRecoveryPlanner
from tools import ToolSandbox


def test_file_error_is_repaired() -> bool:
    sandbox = ToolSandbox()
    graph = build_graph(sandbox, RuleBasedRecoveryPlanner())
    result = graph.invoke(
        initial_state(),
        config={"configurable": {"thread_id": "test-repair"}},
    )

    assert result["status"] == "completed"
    assert result["committed_steps"] == [
        "generate_report",
        "upload_report",
        "create_link",
        "send_email",
    ]
    assert len(sandbox.sent_emails) == 1
    assert any(
        event.startswith("AI PROPOSAL") for event in result["events"]
    )
    print("✓ FILE_NOT_FOUND → AI 修正路径 → 断点续跑")
    return True


def test_unsafe_proposal_is_rejected() -> bool:
    class UnsafePlanner:
        def propose(self, context):
            return {
                "strategy": "patch_step",
                "reason": "尝试调用未授权工具",
                "replacement_step": {
                    "id": context["failed_step"]["id"],
                    "tool": "shell.exec",
                    "args": {"command": "rm -rf /"},
                },
                "resume_from": context["failed_step"]["id"],
            }

    sandbox = ToolSandbox()
    graph = build_graph(sandbox, UnsafePlanner())
    result = graph.invoke(
        initial_state(),
        config={"configurable": {"thread_id": "test-guardrail"}},
    )

    assert result["status"] == "human_review"
    assert any("rejected unsafe" in event for event in result["events"])
    assert sandbox.sent_emails == []
    print("✓ 未授权恢复提案 → 护栏拒绝 → 人工接管")
    return True


def test_invalid_tool_args_are_rejected() -> bool:
    class InvalidArgsPlanner:
        def propose(self, context):
            return {
                "strategy": "patch_step",
                "reason": "提交了 schema 未声明的参数",
                "replacement_step": {
                    "id": context["failed_step"]["id"],
                    "tool": "file.upload",
                    "args": {"url": "https://example.com/report.pdf"},
                },
                "resume_from": context["failed_step"]["id"],
            }

    sandbox = ToolSandbox()
    graph = build_graph(sandbox, InvalidArgsPlanner())
    result = graph.invoke(
        initial_state(),
        config={"configurable": {"thread_id": "test-invalid-args"}},
    )

    assert result["status"] == "human_review"
    assert any("invalid tool args" in event for event in result["events"])
    print("✓ Tool Schema 拒绝缺失 path 的恢复提案")
    return True


def test_recovery_budget_stops_failure_loop() -> bool:
    class StillBrokenPlanner:
        def propose(self, context):
            return {
                "strategy": "patch_step",
                "reason": "仍然使用不存在的路径",
                "replacement_step": {
                    "id": context["failed_step"]["id"],
                    "tool": "file.upload",
                    "args": {"path": "output/still-missing.pdf"},
                },
                "resume_from": context["failed_step"]["id"],
            }

    sandbox = ToolSandbox()
    guard = LoopGuardConfig(
        max_identical_actions=10,
        max_no_progress=10,
    )
    graph = build_graph(sandbox, StillBrokenPlanner(), guard)
    result = graph.invoke(
        initial_state(),
        config={"configurable": {"thread_id": "test-budget"}},
    )

    assert result["status"] == "human_review"
    assert any("BUDGET exhausted" in event for event in result["events"])
    assert result["committed_steps"] == ["generate_report"]
    print("✓ 连续恢复失败达到预算后暂停人工处理")
    return True


def test_silent_upload_failure_is_detected_and_retried() -> bool:
    state = initial_state()
    state["plan"][1]["args"]["path"] = "output/report.pdf"
    sandbox = ToolSandbox(silently_drop_uploads=1)
    graph = build_graph(sandbox, RuleBasedRecoveryPlanner())
    result = graph.invoke(
        state,
        config={"configurable": {"thread_id": "test-silent-failure"}},
    )

    assert result["status"] == "completed"
    assert "output/report.pdf" in sandbox.uploaded
    assert any("POSTCONDITION_FAILED" in event for event in result["events"])
    assert any("AI PROPOSAL retry" in event for event in result["events"])
    assert len(sandbox.sent_emails) == 1
    print("✓ 上传假成功 → 后置条件失败 → AI 重试 → 继续完成")
    return True


def test_repeated_action_loop_is_stopped() -> bool:
    state = initial_state()
    state["plan"][1]["args"]["path"] = "output/report.pdf"
    sandbox = ToolSandbox(silently_drop_uploads=10)
    graph = build_graph(sandbox, RuleBasedRecoveryPlanner())
    result = graph.invoke(
        state,
        config={"configurable": {"thread_id": "test-repeated-action"}},
    )

    assert result["status"] == "human_review"
    assert any("repeated action" in event for event in result["events"])
    print("✓ 连续相同工具调用达到阈值后停止")
    return True


def test_no_progress_loop_is_stopped() -> bool:
    guard = LoopGuardConfig(max_no_progress=1)
    graph = build_graph(ToolSandbox(), RuleBasedRecoveryPlanner(), guard)
    result = graph.invoke(
        initial_state(),
        config={"configurable": {"thread_id": "test-no-progress"}},
    )

    assert result["status"] == "human_review"
    assert any("no observable progress" in event for event in result["events"])
    print("✓ 外部状态无进展达到阈值后停止")
    return True


def test_runtime_budget_is_enforced() -> bool:
    state = initial_state()
    state["started_at"] = 0
    graph = build_graph(ToolSandbox(), RuleBasedRecoveryPlanner())
    result = graph.invoke(
        state,
        config={"configurable": {"thread_id": "test-runtime-budget"}},
    )

    assert result["status"] == "human_review"
    assert any("runtime budget" in event for event in result["events"])
    print("✓ 总运行时间超限后停止")
    return True


def test_execution_budget_is_enforced() -> bool:
    guard = LoopGuardConfig(max_total_executions=0)
    graph = build_graph(ToolSandbox(), RuleBasedRecoveryPlanner(), guard)
    result = graph.invoke(
        initial_state(),
        config={"configurable": {"thread_id": "test-execution-budget"}},
    )

    assert result["status"] == "human_review"
    assert any("execution budget" in event for event in result["events"])
    print("✓ 总执行次数超限后停止")
    return True


def main() -> None:
    tests = [
        test_file_error_is_repaired,
        test_unsafe_proposal_is_rejected,
        test_invalid_tool_args_are_rejected,
        test_recovery_budget_stops_failure_loop,
        test_silent_upload_failure_is_detected_and_retried,
        test_repeated_action_loop_is_stopped,
        test_no_progress_loop_is_stopped,
        test_runtime_budget_is_enforced,
        test_execution_budget_is_enforced,
    ]
    passed = sum(test() for test in tests)
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
