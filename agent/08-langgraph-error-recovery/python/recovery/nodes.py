"""LangGraph node implementations with explicit injected dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from domain.errors import ToolExecutionError
from domain.models import AgentState
from langgraph.types import Command
from tools.runtime import ToolRuntime

from recovery.context import build_failure_context
from recovery.loop_guard import (
    LoopGuardConfig,
    inspect_action,
    no_progress_count,
)
from recovery.planner import RecoveryPlanner

MAX_RECOVERY_ATTEMPTS = 2


@dataclass
class RecoveryNodes:
    runtime: ToolRuntime
    planner: RecoveryPlanner
    loop_guard: LoopGuardConfig

    def execute_step(
        self,
        state: AgentState,
    ) -> Command[Literal["commit_step", "plan_recovery", "human_review"]]:
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
        stalled_count = no_progress_count(
            state["no_progress_count"],
            before_state,
            self.runtime.observable_state(),
        )
        execution_update = {
            "execution_count": execution_count,
            "last_action_signature": signature,
            "repeated_action_count": repeated_count,
            "no_progress_count": stalled_count,
        }
        if stalled_count >= self.loop_guard.max_no_progress:
            return Command(
                update={
                    **execution_update,
                    "events": ["LOOP GUARD no observable progress"],
                },
                goto="human_review",
            )

        recovery_attempts = state["recovery_attempts"] + 1
        context = build_failure_context(
            state,
            step,
            error,
            self.runtime,
            recovery_attempts,
            MAX_RECOVERY_ATTEMPTS,
        )
        if recovery_attempts > MAX_RECOVERY_ATTEMPTS:
            return Command(
                update={
                    "failure_context": context,
                    "recovery_attempts": recovery_attempts,
                    **execution_update,
                    "events": ["RECOVERY BUDGET exhausted"],
                },
                goto="human_review",
            )
        return Command(
            update={
                "failure_context": context,
                "recovery_attempts": recovery_attempts,
                **execution_update,
                "status": "recovering",
                "events": [
                    f"FAILED {step['id']}: {error.code} — route to AI planner"
                ],
            },
            goto="plan_recovery",
        )

    def plan_recovery(
        self,
        state: AgentState,
    ) -> Command[Literal["validate_recovery"]]:
        context = state["failure_context"]
        if context is None:
            raise RuntimeError("Missing failure context")
        proposal = self.planner.propose(context)
        return Command(
            update={
                "recovery_proposal": proposal,
                "events": [
                    f"AI PROPOSAL {proposal['strategy']}: {proposal['reason']}"
                ],
            },
            goto="validate_recovery",
        )

    def validate_recovery(
        self,
        state: AgentState,
    ) -> Command[Literal["execute_step", "human_review"]]:
        proposal = state["recovery_proposal"]
        context = state["failure_context"]
        if proposal is None or context is None:
            raise RuntimeError("Missing recovery proposal or context")
        if proposal["strategy"] == "human":
            return Command(goto="human_review")
        if proposal["resume_from"] != context["failed_step"]["id"]:
            return Command(
                update={"events": ["GUARDRAIL rejected invalid resume_from"]},
                goto="human_review",
            )
        if proposal["strategy"] == "retry":
            if not context["error"]["retryable"]:
                return Command(
                    update={"events": ["GUARDRAIL rejected non-retryable error"]},
                    goto="human_review",
                )
            return Command(
                update={"failure_context": None},
                goto="execute_step",
            )

        replacement = proposal.get("replacement_step")
        allowed = context["constraints"]["allowed_tools"]
        if (
            proposal["strategy"] != "patch_step"
            or replacement is None
            or replacement["tool"] not in allowed
            or replacement["id"] != context["failed_step"]["id"]
        ):
            return Command(
                update={"events": ["GUARDRAIL rejected unsafe proposal"]},
                goto="human_review",
            )

        validation_error = self.runtime.validate_step(replacement)
        if validation_error is not None:
            return Command(
                update={
                    "events": [
                        f"GUARDRAIL rejected invalid tool args: {validation_error}"
                    ]
                },
                goto="human_review",
            )

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

    def human_review(self, state: AgentState) -> dict[str, object]:
        return {
            "status": "human_review",
            "events": ["PAUSED for human review"],
        }

    def done(self, state: AgentState) -> dict[str, object]:
        return {
            "status": "completed",
            "events": ["DONE all steps committed"],
        }
