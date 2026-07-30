"""Extensible tool implementations and registry."""

from tools.builtin import default_tools
from tools.registry import ToolRegistry
from tools.runtime import ToolRuntime
from tools.world import FaultInjector, ToolWorld


def default_runtime(*, silently_drop_uploads: int = 0) -> ToolRuntime:
    """Create the demo runtime with all built-in tools registered."""
    return ToolRuntime(
        registry=ToolRegistry(default_tools()),
        world=ToolWorld(),
        faults=FaultInjector(silently_drop_uploads=silently_drop_uploads),
    )


__all__ = ["ToolRuntime", "default_runtime"]
