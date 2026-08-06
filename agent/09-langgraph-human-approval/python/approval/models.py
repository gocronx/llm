"""State and input contracts for the approval workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

Environment = Literal["staging", "production"]
RiskLevel = Literal["low", "high"]
WorkflowStatus = Literal[
    "pending",
    "awaiting_approval",
    "approved",
    "rejected",
    "completed",
]


class ChangePlan(TypedDict):
    """A deliberately small, mechanically validated production change."""

    action: Literal["scale_service"]
    service: str
    environment: Environment
    replicas: int


class ApprovalState(TypedDict):
    plan: ChangePlan
    revision: int
    risk_level: RiskLevel | None
    risk_reasons: list[str]
    status: WorkflowStatus
    approval_reason: str | None
    executed_plan: ChangePlan | None
    audit_log: Annotated[list[str], operator.add]


def initial_state(plan: ChangePlan) -> ApprovalState:
    """Create complete graph state for a new change request."""
    return {
        "plan": plan,
        "revision": 0,
        "risk_level": None,
        "risk_reasons": [],
        "status": "pending",
        "approval_reason": None,
        "executed_plan": None,
        "audit_log": ["CREATED change request"],
    }
