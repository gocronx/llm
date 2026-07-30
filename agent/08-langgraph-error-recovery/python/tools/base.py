"""Tool extension contract."""

from __future__ import annotations

from typing import Protocol

from domain.models import ToolDefinition

from tools.world import ToolWorld


class Tool(Protocol):
    """Production contract implemented by every executable tool."""

    definition: ToolDefinition

    def execute(
        self,
        args: dict[str, str],
        world: ToolWorld,
    ) -> str: ...

    def verify_effect(
        self,
        args: dict[str, str],
        world: ToolWorld,
    ) -> str | None: ...
