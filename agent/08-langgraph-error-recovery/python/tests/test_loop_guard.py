"""Execution loop-guard cases."""
from __future__ import annotations

from demo_plan import initial_state
from recovery.graph import build_graph
from recovery.loop_guard import LoopGuardConfig
from recovery.planner import RuleBasedRecoveryPlanner
from tools import default_runtime


def test_repeated_action_loop_is_stopped() -> bool:
    state = initial_state()
    state["plan"][1]["args"]["path"] = "output/report.pdf"
    graph = build_graph(
        default_runtime(silently_drop_uploads=10),
        RuleBasedRecoveryPlanner(),
    )
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
    result = build_graph(
        default_runtime(),
        RuleBasedRecoveryPlanner(),
        guard,
    ).invoke(
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
    result = build_graph(default_runtime(), RuleBasedRecoveryPlanner()).invoke(
        state,
        config={"configurable": {"thread_id": "test-runtime-budget"}},
    )
    assert result["status"] == "human_review"
    assert any("runtime budget" in event for event in result["events"])
    print("✓ 总运行时间超限后停止")
    return True


def test_execution_budget_is_enforced() -> bool:
    guard = LoopGuardConfig(max_total_executions=0)
    result = build_graph(
        default_runtime(),
        RuleBasedRecoveryPlanner(),
        guard,
    ).invoke(
        initial_state(),
        config={"configurable": {"thread_id": "test-execution-budget"}},
    )
    assert result["status"] == "human_review"
    assert any("execution budget" in event for event in result["events"])
    print("✓ 总执行次数超限后停止")
    return True


LOOP_GUARD_TESTS = [
    test_repeated_action_loop_is_stopped,
    test_no_progress_loop_is_stopped,
    test_runtime_budget_is_enforced,
    test_execution_budget_is_enforced,
]
