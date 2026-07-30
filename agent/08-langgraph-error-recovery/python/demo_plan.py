"""Initial plan and state used by the runnable demonstration."""

from __future__ import annotations

import time

from domain.models import AgentState, Step


def initial_state() -> AgentState:
    """Create a plan whose upload step intentionally contains a bad path."""
    plan: list[Step] = [
        {
            "id": "generate_report",
            "tool": "report.generate",
            "args": {"output_path": "output/report.pdf"},
        },
        {
            "id": "upload_report",
            "tool": "file.upload",
            "args": {"path": "output/report-final.pdf"},
        },
        {
            "id": "create_link",
            "tool": "link.create",
            "args": {"path": "output/report.pdf"},
        },
        {
            "id": "send_email",
            "tool": "email.send",
            "args": {
                "path": "output/report.pdf",
                "to": "team@example.com",
            },
        },
    ]
    return {
        "goal": "生成项目周报、上传、创建分享链接并发送邮件",
        "plan": plan,
        "current_step": 0,
        "recovery_attempts": 0,
        "execution_count": 0,
        "no_progress_count": 0,
        "last_action_signature": None,
        "repeated_action_count": 0,
        "started_at": time.time(),
        "committed_steps": [],
        "failure_context": None,
        "recovery_proposal": None,
        "status": "running",
        "events": [],
    }
