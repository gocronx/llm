"""Runtime facade combining the registry with external state."""
from __future__ import annotations

from dataclasses import dataclass

from domain.models import Step, ToolDefinition

from tools.registry import ToolRegistry
from tools.world import FaultInjector, ToolWorld


@dataclass
class ToolRuntime:
    registry: ToolRegistry
    world: ToolWorld
    faults: FaultInjector

    def tool_definitions(self) -> list[ToolDefinition]:
        return self.registry.definitions()

    def validate_step(self, step: Step) -> str | None:
        return self.registry.validate_step(step)

    def execute(self, step: Step) -> str:
        return self.registry.execute(step, self.world, self.faults)

    def verify_effect(self, step: Step) -> str | None:
        return self.registry.verify_effect(step, self.world)

    def observable_state(self) -> dict[str, list[str]]:
        return self.world.observable_state()
