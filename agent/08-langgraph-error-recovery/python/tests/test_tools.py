"""Tool registry extensibility tests."""
from __future__ import annotations

from domain.models import ToolDefinition
from tools.base import Tool
from tools.registry import ToolRegistry
from tools.runtime import ToolRuntime
from tools.world import FaultInjector, ToolWorld


class EchoTool:
    definition: ToolDefinition = {
        "name": "text.echo",
        "description": "Echo text without changing central dispatch code.",
        "success_condition": "no side effect required",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    }

    def execute(
        self,
        args: dict[str, str],
        world: ToolWorld,
        faults: FaultInjector,
    ) -> str:
        return args["text"]

    def verify_effect(self, args: dict[str, str], world: ToolWorld) -> str | None:
        return None


def test_custom_tool_registers_without_dispatch_changes() -> bool:
    registry = ToolRegistry([EchoTool()])
    runtime = ToolRuntime(registry, ToolWorld(), FaultInjector())
    result = runtime.execute(
        {"id": "echo", "tool": "text.echo", "args": {"text": "hello"}}
    )
    assert result == "hello"
    assert registry.definitions()[0]["name"] == "text.echo"
    print("✓ 新工具只需实现协议并注册，无需修改中央 dispatch")
    return True


TOOL_TESTS = [test_custom_tool_registers_without_dispatch_changes]
