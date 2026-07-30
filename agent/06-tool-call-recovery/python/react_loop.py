"""Reusable ReAct execution loop and inline tool-call compatibility parser."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from recovery import ToolCallRecovery

Message = dict[str, Any]
LLMCall = Callable[[list[Message]], Message]
Tool = Callable[..., object]

_INLINE_TOOL_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def parse_inline_tool_calls(content: str) -> tuple[list[Message], str]:
    """Parse Qwen-style inline tool calls, preserving malformed source text."""
    matches = list(_INLINE_TOOL_CALL.finditer(content))
    if not matches:
        return [], content

    tool_calls: list[Message] = []
    cleaned = content
    for index, match in enumerate(matches):
        try:
            parsed = json.loads(match.group(1))
            name = parsed.get("name", "")
            arguments = parsed.get("arguments", {})
            if isinstance(arguments, dict):
                arguments = json.dumps(arguments)
            elif not isinstance(arguments, str):
                arguments = "{}"
            tool_calls.append(
                {
                    "id": f"inline-{index}",
                    "function": {"name": name, "arguments": arguments},
                }
            )
            cleaned = cleaned.replace(match.group(0), "")
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
    return tool_calls, cleaned.strip()


def _tool_message(call: Message, name: str, content: str) -> Message:
    """Build the canonical tool-result message used by the loop."""
    return {
        "role": "tool",
        "tool_call_id": call["id"],
        "name": name,
        "content": content,
    }


def _execute_calls(
    calls: list[Message],
    tools: dict[str, Tool],
    recovery: ToolCallRecovery,
) -> list[Message]:
    """Execute tool calls and convert every failure into model-readable context."""
    results: list[Message] = []
    for call in calls:
        function = call["function"]
        name = function["name"]
        if name not in tools:
            error = recovery.handle_unknown_tool(name, list(tools))
            results.append(_tool_message(call, name, error))
            continue
        try:
            arguments = json.loads(function["arguments"] or "{}")
            result = str(tools[name](**arguments))
        except Exception as error:
            result = recovery.wrap_tool_error(name, error)
        results.append(_tool_message(call, name, result))
    return results


def run_robust_react(
    initial_messages: list[Message],
    llm_call: LLMCall,
    recovery: ToolCallRecovery,
    tools: dict[str, Tool],
    max_iterations: int = 8,
) -> tuple[str, list[Message]]:
    """Run a bounded ReAct loop with deterministic recovery guardrails."""
    messages = list(initial_messages)
    for _step in range(max_iterations):
        try:
            response = llm_call(messages)
        except Exception:
            return recovery.recover_empty_response(messages), messages

        content = response.get("content", "")
        calls = response.get("tool_calls", [])
        if recovery.is_empty_response(content, calls):
            if recovery.config.force_summary_on_empty:
                return recovery.recover_empty_response(messages), messages

        if not calls:
            return content, messages

        messages.append({"role": "assistant", "content": content, "tool_calls": calls})
        looped, _name = recovery.detect_repeated_tool_call(messages)
        if looped:
            messages.append(recovery.recover_infinite_loop())
            continue
        messages.extend(_execute_calls(calls, tools, recovery))

    return "", messages
