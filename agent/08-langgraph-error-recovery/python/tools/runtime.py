"""Runtime facade combining the registry with external state."""

from __future__ import annotations

from dataclasses import dataclass

from domain.models import Step, ToolDefinition

from tools.registry import ToolRegistry
from tools.world import ToolWorld


@dataclass
class ToolRuntime:
    """Facade combining tool behavior with externally observable state."""

    registry: ToolRegistry
    world: ToolWorld

    def tool_definitions(self) -> list[ToolDefinition]:
        """Expose planner-safe tool definitions."""
        return self.registry.definitions()

    def validate_step(self, step: Step) -> str | None:
        """Validate a proposed step without executing it."""
        return self.registry.validate_step(step)

    def execute(self, step: Step) -> str:
        """Execute one validated step."""
        return self.registry.execute(step, self.world)

    def verify_effect(self, step: Step) -> str | None:
        """Verify the observable postcondition of one step."""
        return self.registry.verify_effect(step, self.world)

    def observable_state(self) -> dict[str, list[str]]:
        """Return a stable snapshot suitable for progress detection."""
        return self.world.observable_state()
