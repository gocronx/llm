from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from models import (
    AgentState,
    FailureContext,
    RecoveryProposal,
    Step,
)
from planner import RecoveryPlanner
from tools import ToolExecutionError, ToolSandbox, redact_args

MAX_RECOVERY_ATTEMPTS = 2


@dataclass(frozen=True)
class LoopGuardConfig:
    max_total_executions: int = 12
    max_identical_actions: int = 3
    max_no_progress: int = 3
    max_runtime_seconds: float = 120.0


def _fingerprint(state: dict[str, list[str]]) -> str:
    payload = json.dumps(state, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _action_signature(step: Step) -> str:
    args = json.dumps(step["args"], ensure_ascii=False, sort_keys=True)
    return f"{step['tool']}:{args}"


def build_graph(
    sandbox: ToolSandbox,
    planner: RecoveryPlanner,
    loop_guard: LoopGuardConfig | None = None,
):
    """Build the recovery graph around injected tool and planner adapters."""
    guard = loop_guard or LoopGuardConfig()

    def execute_step(
        state: AgentState,
    ) -> Command[Literal["commit_step", "plan_recovery", "human_review"]]:
        step = state["plan"][state["current_step"]]
        if time.time() - state["started_at"] >= guard.max_runtime_seconds:
            return Command(
                update={"events": ["LOOP GUARD runtime budget exhausted"]},
                goto="human_review",
            )
        if state["execution_count"] >= guard.max_total_executions:
            return Command(
                update={"events": ["LOOP GUARD execution budget exhausted"]},
                goto="human_review",
            )

        signature = _action_signature(step)
        repeated_count = (
            state["repeated_action_count"] + 1
            if signature == state["last_action_signature"]
            else 1
        )
        if repeated_count >= guard.max_identical_actions:
            return Command(
                update={"events": [f"LOOP GUARD repeated action: {signature}"]},
                goto="human_review",
            )

        execution_count = state["execution_count"] + 1
        before_fingerprint = _fingerprint(sandbox.observable_state())
        try:
            result = sandbox.execute(step)
            postcondition_error = sandbox.verify_effect(step)
            if postcondition_error is not None:
                raise ToolExecutionError(
                    "POSTCONDITION_FAILED",
                    postcondition_error,
                    retryable=True,
                )
        except ToolExecutionError as error:
            after_fingerprint = _fingerprint(sandbox.observable_state())
            no_progress_count = (
                state["no_progress_count"] + 1
                if before_fingerprint == after_fingerprint
                else 0
            )
            execution_update = {
                "execution_count": execution_count,
                "last_action_signature": signature,
                "repeated_action_count": repeated_count,
                "no_progress_count": no_progress_count,
            }
            if no_progress_count >= guard.max_no_progress:
                return Command(
                    update={
                        **execution_update,
                        "events": ["LOOP GUARD no observable progress"],
                    },
                    goto="human_review",
                )
            recovery_attempts = state["recovery_attempts"] + 1
            context: FailureContext = {
                "goal": state["goal"],
                "committed_steps": state["committed_steps"],
                "failed_step": {
                    **step,
                    "args": redact_args(step["args"]),
                },
                "error": {
                    "code": error.code,
                    "message": str(error),
                    "retryable": error.retryable,
                },
                "observed_state": sandbox.observable_state(),
                "available_tools": sandbox.tool_definitions(),
                "constraints": {
                    "allowed_tools": [
                        definition["name"]
                        for definition in sandbox.tool_definitions()
                    ],
                    "max_recovery_attempts": MAX_RECOVERY_ATTEMPTS,
                    "remaining_recovery_attempts": max(
                        0,
                        MAX_RECOVERY_ATTEMPTS - recovery_attempts,
                    ),
                },
            }
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

        return Command(
            update={
                "execution_count": execution_count,
                "last_action_signature": signature,
                "repeated_action_count": repeated_count,
                "no_progress_count": 0,
                "events": [f"OK {step['id']}: {result}"],
            },
            goto="commit_step",
        )

    def plan_recovery(
        state: AgentState,
    ) -> Command[Literal["validate_recovery"]]:
        context = state["failure_context"]
        if context is None:
            raise RuntimeError("Missing failure context")

        proposal = planner.propose(context)
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

        validation_error = sandbox.validate_step(replacement)
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

    def human_review(state: AgentState) -> dict[str, object]:
        return {
            "status": "human_review",
            "events": ["PAUSED for human review"],
        }

    def done(state: AgentState) -> dict[str, object]:
        return {
            "status": "completed",
            "events": ["DONE all steps committed"],
        }

    builder = StateGraph(AgentState)
    builder.add_node("execute_step", execute_step)
    builder.add_node("plan_recovery", plan_recovery)
    builder.add_node("validate_recovery", validate_recovery)
    builder.add_node("commit_step", commit_step)
    builder.add_node("human_review", human_review)
    builder.add_node("done", done)
    builder.add_edge(START, "execute_step")
    builder.add_edge("human_review", END)
    builder.add_edge("done", END)

    return builder.compile(checkpointer=InMemorySaver())


def initial_state() -> AgentState:
    """Create a plan whose upload step intentionally contains a bad path."""
    plan: list[Step] = [
        {
            "id": "generate_report",
            "tool": "report.generate",
            "args": {"output_path": "output/report.pdf"},
        },
        {
            "id": "upload_report",
            "tool": "file.upload",
            "args": {"path": "output/report-final.pdf"},
        },
        {
            "id": "create_link",
            "tool": "link.create",
            "args": {"path": "output/report.pdf"},
        },
        {
            "id": "send_email",
            "tool": "email.send",
            "args": {
                "path": "output/report.pdf",
                "to": "team@example.com",
            },
        },
    ]
    return {
        "goal": "生成项目周报、上传、创建分享链接并发送邮件",
        "plan": plan,
        "current_step": 0,
        "recovery_attempts": 0,
        "execution_count": 0,
        "no_progress_count": 0,
        "last_action_signature": None,
        "repeated_action_count": 0,
        "started_at": time.time(),
        "committed_steps": [],
        "failure_context": None,
        "recovery_proposal": None,
        "status": "running",
        "events": [],
    }
