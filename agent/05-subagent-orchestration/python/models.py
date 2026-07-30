"""Typed data contracts shared by subagents and their orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class SubAgentResult:
    """Compact result returned without leaking a subagent's message history."""

    status: Literal["completed", "failed", "partial"]
    summary: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    n_iterations: int = 0
    elapsed_ms: float = 0.0
    error: str | None = None
