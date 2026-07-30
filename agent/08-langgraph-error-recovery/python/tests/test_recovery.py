"""Recovery planning, validation, and silent-failure cases."""

from __future__ import annotations

from demo_plan import initial_state
from recovery.graph import build_graph
from recovery.loop_guard import LoopGuardConfig
from recovery.planner import SYSTEM_PROMPT, RuleBasedRecoveryPlanner
from tools import default_runtime

from tests.fakes import runtime_with_silent_upload_failures


def test_file_error_is_repaired() -> bool:
    runtime = default_runtime()
    result = build_graph(runtime, RuleBasedRecoveryPlanner()).invoke(
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
    assert len(runtime.world.sent_emails) == 1
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

    runtime = default_runtime()
    result = build_graph(runtime, UnsafePlanner()).invoke(
        initial_state(),
        config={"configurable": {"thread_id": "test-guardrail"}},
    )
    assert result["status"] == "human_review"
    assert any("rejected unsafe" in event for event in result["events"])
    assert runtime.world.sent_emails == []
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

    result = build_graph(default_runtime(), InvalidArgsPlanner()).invoke(
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

    guard = LoopGuardConfig(max_identical_actions=10, max_no_progress=10)
    result = build_graph(default_runtime(), StillBrokenPlanner(), guard).invoke(
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
    runtime = runtime_with_silent_upload_failures(1)
    result = build_graph(runtime, RuleBasedRecoveryPlanner()).invoke(
        state,
        config={"configurable": {"thread_id": "test-silent-failure"}},
    )
    assert result["status"] == "completed"
    assert "output/report.pdf" in runtime.world.uploaded
    assert any("POSTCONDITION_FAILED" in event for event in result["events"])
    assert any("AI PROPOSAL retry" in event for event in result["events"])
    print("✓ 上传假成功 → 后置条件失败 → AI 重试 → 继续完成")
    return True


def test_planner_contract_exposes_only_supported_strategies() -> bool:
    """Planner 只能看到护栏已实现的恢复策略。"""
    captured_contexts = []

    class CapturingPlanner:
        def propose(self, context):
            captured_contexts.append(context)
            return {
                "strategy": "human",
                "reason": "capture context",
                "resume_from": context["failed_step"]["id"],
            }

    result = build_graph(default_runtime(), CapturingPlanner()).invoke(
        initial_state(),
        config={"configurable": {"thread_id": "test-planner-contract"}},
    )
    assert result["status"] == "human_review"
    assert captured_contexts[0]["constraints"]["allowed_strategies"] == [
        "retry",
        "patch_step",
        "human",
    ]
    assert "replan" not in SYSTEM_PROMPT
    print("✓ Planner 提示词、FailureContext 与护栏策略一致")
    return True


RECOVERY_TESTS = [
    test_file_error_is_repaired,
    test_unsafe_proposal_is_rejected,
    test_invalid_tool_args_are_rejected,
    test_recovery_budget_stops_failure_loop,
    test_silent_upload_failure_is_detected_and_retried,
    test_planner_contract_exposes_only_supported_strategies,
]
