"""Built-in demo tools grouped by a shared in-memory domain."""

from __future__ import annotations

from domain.errors import ToolExecutionError
from domain.models import ToolDefinition

from tools.base import Tool
from tools.world import ToolWorld


class GenerateReportTool:
    """Generate the demo report in the in-memory file store."""

    definition: ToolDefinition = {
        "name": "report.generate",
        "description": "Generate a report and save it to a local path.",
        "success_condition": "output_path exists in observable_state.existing_files",
        "input_schema": {
            "type": "object",
            "properties": {"output_path": {"type": "string"}},
            "required": ["output_path"],
            "additionalProperties": False,
        },
    }

    def execute(
        self,
        args: dict[str, str],
        world: ToolWorld,
    ) -> str:
        """Create a report at ``output_path``."""
        path = args["output_path"]
        world.files[path] = "# 项目周报\n状态：正常"
        return f"generated:{path}"

    def verify_effect(self, args: dict[str, str], world: ToolWorld) -> str | None:
        """Verify that the report exists."""
        path = args["output_path"]
        return None if path in world.files else f"report was not created: {path}"


class UploadFileTool:
    """Upload an existing file."""

    definition: ToolDefinition = {
        "name": "file.upload",
        "description": "Upload an existing local file.",
        "success_condition": "path exists in observable_state.uploaded_files",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    }

    def execute(
        self,
        args: dict[str, str],
        world: ToolWorld,
    ) -> str:
        """Record a successful upload or raise a domain error."""
        path = args["path"]
        if path not in world.files:
            raise ToolExecutionError(
                "FILE_NOT_FOUND",
                f"{path} does not exist",
                retryable=False,
            )
        world.uploaded.add(path)
        return f"uploaded:{path}"

    def verify_effect(self, args: dict[str, str], world: ToolWorld) -> str | None:
        """Verify that the upload was persisted."""
        path = args["path"]
        if path not in world.uploaded:
            return f"upload was acknowledged but not persisted: {path}"
        return None


class CreateLinkTool:
    """Create a share link for an uploaded file."""

    definition: ToolDefinition = {
        "name": "link.create",
        "description": "Create a share link for a file that has been uploaded.",
        "success_condition": "path exists in observable_state.linked_files",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    }

    def execute(
        self,
        args: dict[str, str],
        world: ToolWorld,
    ) -> str:
        """Create and store a share link."""
        path = args["path"]
        if path not in world.uploaded:
            raise ToolExecutionError(
                "FILE_NOT_UPLOADED",
                f"{path} has not been uploaded",
                retryable=False,
            )
        link = f"https://files.example/{path.rsplit('/', 1)[-1]}"
        world.links[path] = link
        return f"linked:{link}"

    def verify_effect(self, args: dict[str, str], world: ToolWorld) -> str | None:
        """Verify that a link exists for the file."""
        path = args["path"]
        return None if path in world.links else f"share link was not created: {path}"


class SendEmailTool:
    """Send the stored share link to a recipient."""

    definition: ToolDefinition = {
        "name": "email.send",
        "description": "Email the share link associated with a file.",
        "success_condition": "an email to `to` exists in observable_state.sent_emails",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "to": {"type": "string"},
            },
            "required": ["path", "to"],
            "additionalProperties": False,
        },
    }

    def execute(
        self,
        args: dict[str, str],
        world: ToolWorld,
    ) -> str:
        """Record an email containing the share link."""
        link = world.links.get(args["path"])
        if link is None:
            raise ToolExecutionError(
                "LINK_NOT_FOUND",
                "No share link exists for the report",
                retryable=False,
            )
        world.sent_emails.append(f"{args['to']} -> {link}")
        return f"sent:{args['to']}"

    def verify_effect(self, args: dict[str, str], world: ToolWorld) -> str | None:
        """Verify that an email was recorded for the recipient."""
        expected_prefix = f"{args['to']} -> "
        if not any(email.startswith(expected_prefix) for email in world.sent_emails):
            return f"email was not recorded for recipient: {args['to']}"
        return None


def default_tools() -> list[Tool]:
    """Return fresh instances of all built-in tools."""
    return [
        GenerateReportTool(),
        UploadFileTool(),
        CreateLinkTool(),
        SendEmailTool(),
    ]
