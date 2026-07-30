"""Test doubles for deterministic failure scenarios."""

from __future__ import annotations

from dataclasses import dataclass

from domain.models import ToolDefinition
from tools.builtin import UploadFileTool, default_tools
from tools.registry import ToolRegistry
from tools.runtime import ToolRuntime
from tools.world import ToolWorld


@dataclass
class SilentlyDroppingUploadTool:
    """A decorator that acknowledges uploads but removes their side effect."""

    wrapped: UploadFileTool
    remaining_failures: int

    @property
    def definition(self) -> ToolDefinition:
        """Reuse the production tool's planner contract."""
        return self.wrapped.definition

    def execute(self, args: dict[str, str], world: ToolWorld) -> str:
        """Execute normally, then hide the effect for a bounded number of calls."""
        result = self.wrapped.execute(args, world)
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            world.uploaded.discard(args["path"])
        return result

    def verify_effect(self, args: dict[str, str], world: ToolWorld) -> str | None:
        """Delegate postcondition verification to the production tool."""
        return self.wrapped.verify_effect(args, world)


def runtime_with_silent_upload_failures(count: int) -> ToolRuntime:
    """Build a runtime whose upload tool silently fails ``count`` times."""
    tools = [
        SilentlyDroppingUploadTool(tool, count)
        if isinstance(tool, UploadFileTool)
        else tool
        for tool in default_tools()
    ]
    return ToolRuntime(ToolRegistry(tools), ToolWorld())
