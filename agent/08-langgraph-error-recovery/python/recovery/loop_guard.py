"""Pure helpers for detecting execution loops and exhausted budgets."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass

from domain.models import AgentState, Step


@dataclass(frozen=True)
class LoopGuardConfig:
    max_total_executions: int = 12
    max_identical_actions: int = 3
    max_no_progress: int = 3
    max_runtime_seconds: float = 120.0


@dataclass(frozen=True)
class ActionGuardResult:
    signature: str
    repeated_count: int
    rejection: str | None = None


def fingerprint(state: dict[str, list[str]]) -> str:
    payload = json.dumps(state, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def inspect_action(
    state: AgentState,
    step: Step,
    config: LoopGuardConfig,
) -> ActionGuardResult:
    if time.time() - state["started_at"] >= config.max_runtime_seconds:
        return ActionGuardResult("", 0, "LOOP GUARD runtime budget exhausted")
    if state["execution_count"] >= config.max_total_executions:
        return ActionGuardResult("", 0, "LOOP GUARD execution budget exhausted")

    args = json.dumps(step["args"], ensure_ascii=False, sort_keys=True)
    signature = f"{step['tool']}:{args}"
    repeated_count = (
        state["repeated_action_count"] + 1
        if signature == state["last_action_signature"]
        else 1
    )
    rejection = None
    if repeated_count >= config.max_identical_actions:
        rejection = f"LOOP GUARD repeated action: {signature}"
    return ActionGuardResult(signature, repeated_count, rejection)


def no_progress_count(
    previous_count: int,
    before: dict[str, list[str]],
    after: dict[str, list[str]],
) -> int:
    return previous_count + 1 if fingerprint(before) == fingerprint(after) else 0
