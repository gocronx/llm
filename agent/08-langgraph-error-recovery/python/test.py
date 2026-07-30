"""不调用真实 LLM 的 LangGraph 恢复测试。"""
from __future__ import annotations

from graph import build_graph, initial_state
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


def main() -> None:
    tests = [
        test_file_error_is_repaired,
        test_unsafe_proposal_is_rejected,
    ]
    passed = sum(test() for test in tests)
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
