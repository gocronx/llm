from __future__ import annotations

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


def build_graph(sandbox: ToolSandbox, planner: RecoveryPlanner):
    """Build the recovery graph around injected tool and planner adapters."""

    def execute_step(
        state: AgentState,
    ) -> Command[Literal["commit_step", "plan_recovery"]]:
        step = state["plan"][state["current_step"]]
        try:
            result = sandbox.execute(step)
        except ToolExecutionError as error:
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
                "constraints": {
                    "allowed_tools": [
                        "report.generate",
                        "file.upload",
                        "link.create",
                        "email.send",
                    ],
                    "max_recovery_steps": 2,
                },
            }
            return Command(
                update={
                    "failure_context": context,
                    "status": "recovering",
                    "events": [
                        f"FAILED {step['id']}: {error.code} — route to AI planner"
                    ],
                },
                goto="plan_recovery",
            )

        return Command(
            update={"events": [f"OK {step['id']}: {result}"]},
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
        "committed_steps": [],
        "failure_context": None,
        "recovery_proposal": None,
        "status": "running",
        "events": [],
    }
