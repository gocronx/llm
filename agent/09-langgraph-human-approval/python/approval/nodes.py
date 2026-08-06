"""LangGraph nodes for risk routing, approval, and execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from langgraph.types import Command, interrupt

from approval.models import ApprovalState
from approval.policy import assess_risk, validate_decision, validate_plan


@dataclass(frozen=True)
class ApprovalNodes:
    """Coordinate pure policies while keeping graph state explicit."""

    def assess_risk(
        self,
        state: ApprovalState,
    ) -> Command[Literal["request_approval", "execute"]]:
        assessment = assess_risk(state["plan"])
        if assessment.level == "high":
            return Command(
                update={
                    "risk_level": assessment.level,
                    "risk_reasons": list(assessment.reasons),
                    "status": "awaiting_approval",
                    "audit_log": [
                        f"HIGH_RISK revision={state['revision']}: "
                        + "; ".join(assessment.reasons)
                    ],
                },
                goto="request_approval",
            )
        return Command(
            update={
                "risk_level": assessment.level,
                "risk_reasons": list(assessment.reasons),
                "status": "approved",
                "audit_log": [
                    f"LOW_RISK revision={state['revision']}: automatic approval"
                ],
            },
            goto="execute",
        )

    def request_approval(
        self,
        state: ApprovalState,
    ) -> Command[Literal["assess_risk", "execute", "rejected"]]:
        raw_decision = interrupt(
            {
                "kind": "change_approval",
                "revision": state["revision"],
                "risk_level": state["risk_level"],
                "risk_reasons": state["risk_reasons"],
                "plan": state["plan"],
                "allowed_actions": ["approve", "edit", "reject"],
            }
        )
        decision = validate_decision(raw_decision, current_plan=state["plan"])
        if decision.action == "approve":
            return Command(
                update={
                    "status": "approved",
                    "approval_reason": decision.reason,
                    "audit_log": [f"APPROVED: {decision.reason}"],
                },
                goto="execute",
            )
        if decision.action == "reject":
            return Command(
                update={
                    "status": "rejected",
                    "approval_reason": decision.reason,
                    "audit_log": [f"REJECTED: {decision.reason}"],
                },
                goto="rejected",
            )
        if decision.edited_plan is None:
            raise RuntimeError("validated edit is missing edited_plan")
        return Command(
            update={
                "plan": decision.edited_plan,
                "revision": state["revision"] + 1,
                "risk_level": None,
                "risk_reasons": [],
                "status": "pending",
                "approval_reason": decision.reason,
                "audit_log": [f"EDITED: {decision.reason}"],
            },
            goto="assess_risk",
        )

    def execute(self, state: ApprovalState) -> dict:
        """Execute only a validated plan that reached an approved route."""
        if state["status"] != "approved":
            raise RuntimeError("execution requires approved state")
        plan = validate_plan(state["plan"])
        return {
            "executed_plan": dict(plan),
            "status": "completed",
            "audit_log": [
                "EXECUTED "
                f"{plan['action']} {plan['service']} "
                f"environment={plan['environment']} replicas={plan['replicas']}"
            ],
        }

    def rejected(self, state: ApprovalState) -> dict:
        """Terminate without executing the rejected plan."""
        return {"status": "rejected", "audit_log": ["STOPPED without execution"]}
