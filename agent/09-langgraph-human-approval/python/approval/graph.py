"""LangGraph topology for durable human approval."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from approval.models import ApprovalState
from approval.nodes import ApprovalNodes


def build_graph(checkpointer: Any | None = None) -> CompiledStateGraph:
    """Compile the workflow with an injectable durable checkpointer."""
    nodes = ApprovalNodes()
    builder = StateGraph(ApprovalState)
    builder.add_node("assess_risk", nodes.assess_risk)
    builder.add_node("request_approval", nodes.request_approval)
    builder.add_node("execute", nodes.execute)
    builder.add_node("rejected", nodes.rejected)
    builder.add_edge(START, "assess_risk")
    builder.add_edge("execute", END)
    builder.add_edge("rejected", END)
    return builder.compile(checkpointer=checkpointer or InMemorySaver())
