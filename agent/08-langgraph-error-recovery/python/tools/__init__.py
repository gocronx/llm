"""Extensible tool implementations and registry."""

from tools.builtin import default_tools
from tools.registry import ToolRegistry
from tools.runtime import ToolRuntime
from tools.world import ToolWorld


def default_runtime() -> ToolRuntime:
    """Create the demo runtime with all built-in tools registered."""
    return ToolRuntime(
        registry=ToolRegistry(default_tools()),
        world=ToolWorld(),
    )


__all__ = ["ToolRuntime", "default_runtime"]
