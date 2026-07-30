from __future__ import annotations

import operator
from typing import Annotated, Literal, NotRequired, TypedDict


class Step(TypedDict):
    id: str
    tool: str
    args: dict[str, str]


class ToolDefinition(TypedDict):
    name: str
    description: str
    input_schema: dict[str, object]


class ToolErrorInfo(TypedDict):
    code: str
    message: str
    retryable: bool


class FailureContext(TypedDict):
    goal: str
    committed_steps: list[str]
    failed_step: Step
    error: ToolErrorInfo
    observed_state: dict[str, list[str]]
    available_tools: list[ToolDefinition]
    constraints: dict[str, object]


class RecoveryProposal(TypedDict):
    strategy: Literal["retry", "patch_step", "replan", "human"]
    reason: str
    replacement_step: NotRequired[Step]
    resume_from: str


class AgentState(TypedDict):
    goal: str
    plan: list[Step]
    current_step: int
    recovery_attempts: int
    committed_steps: list[str]
    failure_context: FailureContext | None
    recovery_proposal: RecoveryProposal | None
    status: Literal["running", "recovering", "completed", "human_review"]
    events: Annotated[list[str], operator.add]
