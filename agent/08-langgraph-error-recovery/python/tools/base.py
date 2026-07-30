"""Tool extension contract."""
from __future__ import annotations

from typing import Protocol

from domain.models import ToolDefinition

from tools.world import FaultInjector, ToolWorld


class Tool(Protocol):
    definition: ToolDefinition

    def execute(
        self,
        args: dict[str, str],
        world: ToolWorld,
        faults: FaultInjector,
    ) -> str: ...

    def verify_effect(
        self,
        args: dict[str, str],
        world: ToolWorld,
    ) -> str | None: ...
