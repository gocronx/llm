"""LangGraph node implementations with explicit injected dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from domain.errors import ToolExecutionError
from domain.models import AgentState, TerminalUpdate
from langgraph.types import Command
from tools.runtime import ToolRuntime

from recovery.failure import assess_failure
from recovery.loop_guard import LoopGuardConfig, inspect_action
from recovery.planner import RecoveryPlanner
from recovery.policy import validate_recovery_proposal

MAX_RECOVERY_ATTEMPTS = 2


@dataclass
class RecoveryNodes:
    """LangGraph nodes that coordinate execution and pure recovery policies."""

    runtime: ToolRuntime
    planner: RecoveryPlanner
    loop_guard: LoopGuardConfig

    def execute_step(
        self,
        state: AgentState,
    ) -> Command[Literal["commit_step", "plan_recovery", "human_review"]]:
        """Execute one plan step and route success or failure."""
        step = state["plan"][state["current_step"]]
        action = inspect_action(state, step, self.loop_guard)
        if action.rejection is not None:
            return Command(
                update={"events": [action.rejection]},
                goto="human_review",
            )

        execution_count = state["execution_count"] + 1
        before_state = self.runtime.observable_state()
        try:
            result = self.runtime.execute(step)
            postcondition_error = self.runtime.verify_effect(step)
            if postcondition_error is not None:
                raise ToolExecutionError(
                    "POSTCONDITION_FAILED",
                    postcondition_error,
                    retryable=True,
                )
        except ToolExecutionError as error:
            return self._handle_failure(
                state,
                error,
                before_state,
                execution_count,
                action.signature,
                action.repeated_count,
            )

        return Command(
            update={
                "execution_count": execution_count,
                "last_action_signature": action.signature,
                "repeated_action_count": action.repeated_count,
                "no_progress_count": 0,
                "events": [f"OK {step['id']}: {result}"],
            },
            goto="commit_step",
        )

    def _handle_failure(
        self,
        state: AgentState,
        error: ToolExecutionError,
        before_state: dict[str, list[str]],
        execution_count: int,
        signature: str,
        repeated_count: int,
    ) -> Command[Literal["plan_recovery", "human_review"]]:
        step = state["plan"][state["current_step"]]
        assessment = assess_failure(
            state,
            step,
            error,
            self.runtime,
            self.loop_guard,
            execution_count,
            signature,
            repeated_count,
            before_state,
            MAX_RECOVERY_ATTEMPTS,
        )
        if assessment.terminal_event is not None:
            return Command(
                update={
                    "failure_context": assessment.context,
                    "recovery_attempts": assessment.recovery_attempts,
                    **assessment.execution_update,
                    "events": [assessment.terminal_event],
                },
                goto="human_review",
            )
        return Command(
            update={
                "failure_context": assessment.context,
                "recovery_attempts": assessment.recovery_attempts,
                **assessment.execution_update,
                "status": "recovering",
                "events": [f"FAILED {step['id']}: {error.code} — route to AI planner"],
            },
            goto="plan_recovery",
        )

    def plan_recovery(
        self,
        state: AgentState,
    ) -> Command[Literal["validate_recovery"]]:
        """Ask the recovery planner for a structured proposal."""
        context = state["failure_context"]
        if context is None:
            raise RuntimeError("Missing failure context")
        proposal = self.planner.propose(context)
        return Command(
            update={
                "recovery_proposal": proposal,
                "events": [f"AI PROPOSAL {proposal['strategy']}: {proposal['reason']}"],
            },
            goto="validate_recovery",
        )

    def validate_recovery(
        self,
        state: AgentState,
    ) -> Command[Literal["execute_step", "human_review"]]:
        """Apply only recovery proposals accepted by deterministic policy."""
        proposal = state["recovery_proposal"]
        context = state["failure_context"]
        if proposal is None or context is None:
            raise RuntimeError("Missing recovery proposal or context")
        decision = validate_recovery_proposal(proposal, context, self.runtime)
        if decision.action == "human":
            update = {"events": [decision.event]} if decision.event else None
            return Command(update=update, goto="human_review")
        if decision.action == "retry":
            return Command(
                update={"failure_context": None},
                goto="execute_step",
            )
        replacement = decision.replacement
        if replacement is None:
            raise RuntimeError("Patch decision is missing replacement step")
        patched_plan = list(state["plan"])
        patched_plan[state["current_step"]] = replacement
        return Command(
            update={
                "plan": patched_plan,
                "failure_context": None,
                "events": ["GUARDRAIL approved patched step"],
            },
            goto="execute_step",
        )

    def commit_step(
        self,
        state: AgentState,
    ) -> Command[Literal["execute_step", "done"]]:
        """Commit a successful step and advance the plan cursor."""
        step = state["plan"][state["current_step"]]
        next_index = state["current_step"] + 1
        goto: Literal["execute_step", "done"] = (
            "done" if next_index == len(state["plan"]) else "execute_step"
        )
        return Command(
            update={
                "current_step": next_index,
                "committed_steps": [*state["committed_steps"], step["id"]],
                "status": "running",
                "recovery_attempts": 0,
            },
            goto=goto,
        )

    def human_review(self, state: AgentState) -> TerminalUpdate:
        """Pause execution for human intervention."""
        return {
            "status": "human_review",
            "events": ["PAUSED for human review"],
        }

    def done(self, state: AgentState) -> TerminalUpdate:
        """Mark the workflow complete."""
        return {
            "status": "completed",
            "events": ["DONE all steps committed"],
        }
