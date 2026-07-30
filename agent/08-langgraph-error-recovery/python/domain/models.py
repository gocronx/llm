from __future__ import annotations

import operator
from typing import Annotated, Final, Literal, NotRequired, TypedDict

RecoveryStrategy = Literal["retry", "patch_step", "human"]
ALLOWED_RECOVERY_STRATEGIES: Final[tuple[RecoveryStrategy, ...]] = (
    "retry",
    "patch_step",
    "human",
)


class PropertySchema(TypedDict):
    """Supported JSON Schema subset for one tool argument."""

    type: Literal["string"]


class InputSchema(TypedDict):
    """Strongly typed JSON Schema subset accepted by the demo registry."""

    type: Literal["object"]
    properties: dict[str, PropertySchema]
    required: list[str]
    additionalProperties: bool


class Step(TypedDict):
    id: str
    tool: str
    args: dict[str, str]


class ToolDefinition(TypedDict):
    """Tool metadata shared by the planner and execution registry."""

    name: str
    description: str
    input_schema: InputSchema
    success_condition: str


class ToolErrorInfo(TypedDict):
    code: str
    message: str
    retryable: bool


class RecoveryConstraints(TypedDict):
    """Mechanical limits supplied to a recovery planner."""

    allowed_tools: list[str]
    allowed_strategies: list[RecoveryStrategy]
    max_recovery_attempts: int
    remaining_recovery_attempts: int


class ExecutionUpdate(TypedDict):
    """Counters recorded after each tool execution attempt."""

    execution_count: int
    last_action_signature: str
    repeated_action_count: int
    no_progress_count: int


class TerminalUpdate(TypedDict):
    """Minimal state update emitted by terminal graph nodes."""

    status: Literal["completed", "human_review"]
    events: list[str]


class FailureContext(TypedDict):
    goal: str
    committed_steps: list[str]
    failed_step: Step
    error: ToolErrorInfo
    observed_state: dict[str, list[str]]
    available_tools: list[ToolDefinition]
    constraints: RecoveryConstraints


class RecoveryProposal(TypedDict):
    strategy: RecoveryStrategy
    reason: str
    replacement_step: NotRequired[Step]
    resume_from: str


class AgentState(TypedDict):
    goal: str
    plan: list[Step]
    current_step: int
    recovery_attempts: int
    execution_count: int
    no_progress_count: int
    last_action_signature: str | None
    repeated_action_count: int
    started_at: float
    committed_steps: list[str]
    failure_context: FailureContext | None
    recovery_proposal: RecoveryProposal | None
    status: Literal["running", "recovering", "completed", "human_review"]
    events: Annotated[list[str], operator.add]
