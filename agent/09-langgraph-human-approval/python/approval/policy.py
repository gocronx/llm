"""Pure validation and risk policy, independent of LangGraph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, cast

from approval.models import ChangePlan, RiskLevel

PLAN_FIELDS = {"action", "service", "environment", "replicas"}
IMMUTABLE_PLAN_FIELDS = ("action", "service")


class DecisionError(ValueError):
    """Raised when an approval response violates the decision contract."""


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ValidatedDecision:
    action: Literal["approve", "edit", "reject"]
    reason: str
    edited_plan: ChangePlan | None = None


def validate_plan(value: object) -> ChangePlan:
    """Validate the exact plan schema before risk assessment or execution."""
    if not isinstance(value, Mapping) or set(value) != PLAN_FIELDS:
        raise DecisionError(f"plan must contain exactly {sorted(PLAN_FIELDS)}")
    if value["action"] != "scale_service":
        raise DecisionError("only scale_service is allowed")
    if not isinstance(value["service"], str) or not value["service"].strip():
        raise DecisionError("service must be a non-empty string")
    if value["environment"] not in {"staging", "production"}:
        raise DecisionError("environment must be staging or production")
    replicas = value["replicas"]
    if isinstance(replicas, bool) or not isinstance(replicas, int):
        raise DecisionError("replicas must be an integer")
    if not 1 <= replicas <= 20:
        raise DecisionError("replicas must be between 1 and 20")
    return cast(ChangePlan, dict(value))


def assess_risk(plan: ChangePlan) -> RiskAssessment:
    """Classify risk with deterministic rules rather than model judgment."""
    validated = validate_plan(plan)
    reasons: list[str] = []
    if validated["environment"] == "production":
        reasons.append("targets production")
    if validated["replicas"] >= 4:
        reasons.append("requests four or more replicas")
    if reasons:
        return RiskAssessment(level="high", reasons=tuple(reasons))
    return RiskAssessment(
        level="low", reasons=("staging change within capacity limit",)
    )


def validate_decision(
    value: object,
    *,
    current_plan: ChangePlan,
) -> ValidatedDecision:
    """Reject ambiguous or over-privileged human resume payloads."""
    if not isinstance(value, Mapping):
        raise DecisionError("decision must be an object")
    action = value.get("action")
    if action not in {"approve", "edit", "reject"}:
        raise DecisionError("action must be approve, edit, or reject")
    expected_fields = (
        {"action", "reason", "edited_plan"}
        if action == "edit"
        else {
            "action",
            "reason",
        }
    )
    if set(value) != expected_fields:
        raise DecisionError(
            f"{action} decision must contain exactly {sorted(expected_fields)}"
        )
    reason = value.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise DecisionError("reason must be a non-empty string")
    if action != "edit":
        return ValidatedDecision(action=action, reason=reason.strip())

    edited = validate_plan(value.get("edited_plan"))
    for field in IMMUTABLE_PLAN_FIELDS:
        if edited[field] != current_plan[field]:
            raise DecisionError(f"edit cannot change immutable field: {field}")
    return ValidatedDecision(action="edit", reason=reason.strip(), edited_plan=edited)
