"""LangGraph topology for execution and recovery."""

from __future__ import annotations

from domain.models import AgentState
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from tools.runtime import ToolRuntime

from recovery.loop_guard import LoopGuardConfig
from recovery.nodes import RecoveryNodes
from recovery.planner import RecoveryPlanner


def build_graph(
    runtime: ToolRuntime,
    planner: RecoveryPlanner,
    loop_guard: LoopGuardConfig | None = None,
) -> CompiledStateGraph:
    """Compile the recovery workflow with injected runtime and planner."""
    nodes = RecoveryNodes(
        runtime=runtime,
        planner=planner,
        loop_guard=loop_guard or LoopGuardConfig(),
    )
    builder = StateGraph(AgentState)
    builder.add_node("execute_step", nodes.execute_step)
    builder.add_node("plan_recovery", nodes.plan_recovery)
    builder.add_node("validate_recovery", nodes.validate_recovery)
    builder.add_node("commit_step", nodes.commit_step)
    builder.add_node("human_review", nodes.human_review)
    builder.add_node("done", nodes.done)
    builder.add_edge(START, "execute_step")
    builder.add_edge("human_review", END)
    builder.add_edge("done", END)
    return builder.compile(checkpointer=InMemorySaver())
