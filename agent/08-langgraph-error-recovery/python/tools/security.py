"""Prompt-boundary security helpers."""

from __future__ import annotations

from typing import Any


def redact_args(args: dict[str, Any]) -> dict[str, Any]:
    """Redact common secrets before tool arguments enter an AI prompt."""
    secret_keys = {"token", "password", "api_key", "authorization"}
    return {
        key: "***REDACTED***" if key.lower() in secret_keys else value
        for key, value in args.items()
    }
