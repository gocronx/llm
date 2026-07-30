"""Pure validation policy for AI-generated recovery proposals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from domain.models import FailureContext, RecoveryProposal, Step


class StepValidator(Protocol):
    """Minimal dependency needed to validate a proposed tool call."""

    def validate_step(self, step: Step) -> str | None:
        """Return a validation error or ``None`` when the step is valid."""


@dataclass(frozen=True)
class RecoveryDecision:
    """Validated action that orchestration code may safely apply."""

    action: Literal["retry", "patch", "human"]
    event: str | None = None
    replacement: Step | None = None


def validate_recovery_proposal(
    proposal: RecoveryProposal,
    context: FailureContext,
    validator: StepValidator,
) -> RecoveryDecision:
    """Validate a recovery proposal without mutating graph state.

    Args:
        proposal: AI-generated structured recovery proposal.
        context: Failure context and mechanical constraints.
        validator: Tool-call schema validator.

    Returns:
        A safe orchestration decision.
    """
    if proposal["strategy"] == "human":
        return RecoveryDecision("human")
    if proposal["resume_from"] != context["failed_step"]["id"]:
        return RecoveryDecision("human", "GUARDRAIL rejected invalid resume_from")
    if proposal["strategy"] == "retry":
        if context["error"]["retryable"]:
            return RecoveryDecision("retry")
        return RecoveryDecision("human", "GUARDRAIL rejected non-retryable error")

    replacement = proposal.get("replacement_step")
    if (
        proposal["strategy"] != "patch_step"
        or replacement is None
        or replacement["tool"] not in context["constraints"]["allowed_tools"]
        or replacement["id"] != context["failed_step"]["id"]
    ):
        return RecoveryDecision("human", "GUARDRAIL rejected unsafe proposal")

    validation_error = validator.validate_step(replacement)
    if validation_error is not None:
        event = f"GUARDRAIL rejected invalid tool args: {validation_error}"
        return RecoveryDecision("human", event)
    return RecoveryDecision("patch", replacement=replacement)
