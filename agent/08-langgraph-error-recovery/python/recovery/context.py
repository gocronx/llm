"""Failure-context construction for recovery planners."""

from __future__ import annotations

from domain.errors import ToolExecutionError
from domain.models import (
    ALLOWED_RECOVERY_STRATEGIES,
    AgentState,
    FailureContext,
    Step,
)
from tools.runtime import ToolRuntime
from tools.security import redact_args


def build_failure_context(
    state: AgentState,
    step: Step,
    error: ToolExecutionError,
    runtime: ToolRuntime,
    recovery_attempts: int,
    max_recovery_attempts: int,
) -> FailureContext:
    definitions = runtime.tool_definitions()
    return {
        "goal": state["goal"],
        "committed_steps": state["committed_steps"],
        "failed_step": {**step, "args": redact_args(step["args"])},
        "error": {
            "code": error.code,
            "message": str(error),
            "retryable": error.retryable,
        },
        "observed_state": runtime.observable_state(),
        "available_tools": definitions,
        "constraints": {
            "allowed_tools": [definition["name"] for definition in definitions],
            "allowed_strategies": list(ALLOWED_RECOVERY_STRATEGIES),
            "max_recovery_attempts": max_recovery_attempts,
            "remaining_recovery_attempts": max(
                0,
                max_recovery_attempts - recovery_attempts,
            ),
        },
    }
