from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from models import Step, ToolDefinition

TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    {
        "name": "report.generate",
        "description": "Generate a report and save it to a local path.",
        "input_schema": {
            "type": "object",
            "properties": {"output_path": {"type": "string"}},
            "required": ["output_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "file.upload",
        "description": "Upload an existing local file.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "link.create",
        "description": "Create a share link for a file that has been uploaded.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "email.send",
        "description": "Email the share link associated with a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "to": {"type": "string"},
            },
            "required": ["path", "to"],
            "additionalProperties": False,
        },
    },
)


class ToolExecutionError(Exception):
    """A structured, LLM-recoverable tool failure."""

    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass
class ToolSandbox:
    """In-memory external world used by the demo."""

    files: dict[str, str] = field(default_factory=dict)
    uploaded: set[str] = field(default_factory=set)
    links: dict[str, str] = field(default_factory=dict)
    sent_emails: list[str] = field(default_factory=list)

    def tool_definitions(self) -> list[ToolDefinition]:
        """Return copies safe to include in an AI prompt."""
        return copy.deepcopy(list(TOOL_DEFINITIONS))

    def validate_step(self, step: Step) -> str | None:
        """Validate a proposed call against the registered tool schema."""
        definition = next(
            (item for item in TOOL_DEFINITIONS if item["name"] == step["tool"]),
            None,
        )
        if definition is None:
            return f"unknown tool: {step['tool']}"

        schema = definition["input_schema"]
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

    def execute(self, step: Step) -> str:
        validation_error = self.validate_step(step)
        if validation_error is not None:
            raise ToolExecutionError(
                "INVALID_TOOL_ARGS",
                validation_error,
                retryable=False,
            )
        tool = step["tool"]
        args = step["args"]

        if tool == "report.generate":
            path = args["output_path"]
            self.files[path] = "# 项目周报\n状态：正常"
            return f"generated:{path}"

        if tool == "file.upload":
            path = args["path"]
            if path not in self.files:
                raise ToolExecutionError(
                    "FILE_NOT_FOUND",
                    f"{path} does not exist",
                    retryable=False,
                )
            self.uploaded.add(path)
            return f"uploaded:{path}"

        if tool == "link.create":
            path = args["path"]
            if path not in self.uploaded:
                raise ToolExecutionError(
                    "FILE_NOT_UPLOADED",
                    f"{path} has not been uploaded",
                    retryable=False,
                )
            link = f"https://files.example/{path.rsplit('/', 1)[-1]}"
            self.links[path] = link
            return f"linked:{link}"

        if tool == "email.send":
            link = self.links.get(args["path"])
            if link is None:
                raise ToolExecutionError(
                    "LINK_NOT_FOUND",
                    "No share link exists for the report",
                    retryable=False,
                )
            self.sent_emails.append(f"{args['to']} -> {link}")
            return f"sent:{args['to']}"

        raise ToolExecutionError(
            "TOOL_NOT_ALLOWED",
            f"Unknown tool: {tool}",
            retryable=False,
        )

    def observable_state(self) -> dict[str, list[str]]:
        return {
            "existing_files": sorted(self.files),
            "uploaded_files": sorted(self.uploaded),
            "linked_files": sorted(self.links),
        }


def redact_args(args: dict[str, Any]) -> dict[str, Any]:
    """Redact common secrets before tool arguments enter an AI prompt."""
    secret_keys = {"token", "password", "api_key", "authorization"}
    return {
        key: "***REDACTED***" if key.lower() in secret_keys else value
        for key, value in args.items()
    }
