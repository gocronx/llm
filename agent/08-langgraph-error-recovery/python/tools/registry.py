"""Tool registration, schema validation, and dispatch."""
from __future__ import annotations

import copy

from domain.errors import ToolExecutionError
from domain.models import Step, ToolDefinition

from tools.base import Tool
from tools.world import FaultInjector, ToolWorld


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        name = tool.definition["name"]
        if name in self._tools:
            raise ValueError(f"duplicate tool registration: {name}")
        self._tools[name] = tool

    def definitions(self) -> list[ToolDefinition]:
        return copy.deepcopy([tool.definition for tool in self._tools.values()])

    def validate_step(self, step: Step) -> str | None:
        tool = self._tools.get(step["tool"])
        if tool is None:
            return f"unknown tool: {step['tool']}"

        schema = tool.definition["input_schema"]
        args = step["args"]
        required = set(schema.get("required", []))
        missing = sorted(required - args.keys())
        if missing:
            return f"missing required args: {', '.join(missing)}"

        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            return "invalid tool schema"
        extra = sorted(args.keys() - properties.keys())
        if schema.get("additionalProperties") is False and extra:
            return f"unexpected args: {', '.join(extra)}"

        for name, value in args.items():
            property_schema = properties.get(name, {})
            if isinstance(property_schema, dict):
                expected = property_schema.get("type")
                if expected == "string" and not isinstance(value, str):
                    return f"arg {name} must be a string"
        return None

    def execute(
        self,
        step: Step,
        world: ToolWorld,
        faults: FaultInjector,
    ) -> str:
        validation_error = self.validate_step(step)
        if validation_error is not None:
            raise ToolExecutionError(
                "INVALID_TOOL_ARGS",
                validation_error,
                retryable=False,
            )
        return self._tools[step["tool"]].execute(step["args"], world, faults)

    def verify_effect(self, step: Step, world: ToolWorld) -> str | None:
        return self._tools[step["tool"]].verify_effect(step["args"], world)
