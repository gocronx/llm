from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from models import Step


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

    def execute(self, step: Step) -> str:
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
