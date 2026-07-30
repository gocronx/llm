"""Failure accounting shared by execution nodes."""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import ToolExecutionError
from domain.models import AgentState, ExecutionUpdate, FailureContext, Step
from tools.runtime import ToolRuntime

from recovery.context import build_failure_context
from recovery.loop_guard import LoopGuardConfig, no_progress_count


@dataclass(frozen=True)
class FailureAssessment:
    """Computed state updates and optional terminal guard event."""

    execution_update: ExecutionUpdate
    recovery_attempts: int
    context: FailureContext
    terminal_event: str | None


def assess_failure(
    state: AgentState,
    step: Step,
    error: ToolExecutionError,
    runtime: ToolRuntime,
    loop_guard: LoopGuardConfig,
    execution_count: int,
    signature: str,
    repeated_count: int,
    before_state: dict[str, list[str]],
    max_recovery_attempts: int,
) -> FailureAssessment:
    """Calculate failure counters, context, and terminal guard decisions."""
    stalled_count = no_progress_count(
        state["no_progress_count"],
        before_state,
        runtime.observable_state(),
    )
    execution_update: ExecutionUpdate = {
        "execution_count": execution_count,
        "last_action_signature": signature,
        "repeated_action_count": repeated_count,
        "no_progress_count": stalled_count,
    }
    recovery_attempts = state["recovery_attempts"] + 1
    context = build_failure_context(
        state,
        step,
        error,
        runtime,
        recovery_attempts,
        max_recovery_attempts,
    )
    terminal_event = None
    if stalled_count >= loop_guard.max_no_progress:
        terminal_event = "LOOP GUARD no observable progress"
    elif recovery_attempts > max_recovery_attempts:
        terminal_event = "RECOVERY BUDGET exhausted"
    return FailureAssessment(
        execution_update,
        recovery_attempts,
        context,
        terminal_event,
    )
