"""Layered guardrails wrapping the raw tools. invoke() runs all checks then dispatches."""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import audit
from tools import SEVERITY, TOOLS, WORKSPACE

ALLOWED_PATH_PREFIXES = [WORKSPACE.resolve()]

_DANGEROUS_SHELL = re.compile(
    r"(rm\s+-rf\s+/|:(){.*};:|>\s*/dev/sd|chmod\s+777\s+/|"
    r"curl[^|]*\|\s*(sh|bash)|wget[^|]*\|\s*(sh|bash)|"
    r"mkfs\.|dd\s+if=|format\s+c:)",
    re.IGNORECASE,
)

_INTERNAL_HOST = re.compile(
    r"^https?://(localhost|127\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.|"
    r"169\.254\.|metadata\.google|169\.254\.169\.254)",
    re.IGNORECASE,
)


class Blocked(Exception):
    """A guardrail refused the tool call."""


@dataclass(frozen=True)
class RateLimit:
    window_seconds: int
    max_calls: int


LIMITS: dict[str, RateLimit] = {
    "low":    RateLimit(window_seconds=60, max_calls=30),
    "medium": RateLimit(window_seconds=60, max_calls=10),
    "high":   RateLimit(window_seconds=60, max_calls=3),
}

_recent: dict[str, deque[float]] = {sev: deque() for sev in LIMITS}


def _path_in_workspace(raw: str) -> bool:
    try:
        resolved = Path(raw).resolve()
    except OSError:
        return False
    return any(resolved == p or p in resolved.parents for p in ALLOWED_PATH_PREFIXES)


def _check_path(tool: str, args: dict) -> str | None:
    if tool not in {"read_file", "write_file", "delete_file"}:
        return None
    path = args.get("path", "")
    if not _path_in_workspace(path):
        return f"path {path!r} is outside workspace {WORKSPACE}"
    if ".." in Path(path).parts:
        return f"path {path!r} contains .. traversal"
    return None


def _check_dangerous_args(tool: str, args: dict) -> str | None:
    if tool == "run_shell":
        cmd = args.get("cmd", "")
        if _DANGEROUS_SHELL.search(cmd):
            return f"shell command matches dangerous pattern: {cmd[:60]}"
    if tool == "http_get":
        url = args.get("url", "")
        if _INTERNAL_HOST.search(url):
            return f"URL targets internal/cloud-metadata host: {url}"
    return None


def _check_rate(tool: str, _args: dict) -> str | None:
    sev = SEVERITY.get(tool, "medium")
    limit = LIMITS[sev]
    cutoff = time.time() - limit.window_seconds
    dq = _recent[sev]
    while dq and dq[0] < cutoff:
        dq.popleft()
    if len(dq) >= limit.max_calls:
        return (f"rate limit: {len(dq)} {sev}-severity calls in last "
                f"{limit.window_seconds}s (max {limit.max_calls})")
    return None


CHECKS: list[Callable[[str, dict], str | None]] = [
    _check_path,
    _check_dangerous_args,
    _check_rate,
]


def _needs_confirmation(tool: str) -> bool:
    return SEVERITY.get(tool) == "high"


def _record_call(tool: str) -> None:
    _recent[SEVERITY.get(tool, "medium")].append(time.time())


def invoke(tool: str, args: dict, *, auto_confirm: bool = False) -> object:
    if tool not in TOOLS:
        audit.record(tool, args, "block", reason="unknown tool")
        raise Blocked(f"unknown tool: {tool}")

    for check in CHECKS:
        reason = check(tool, args)
        if reason:
            audit.record(tool, args, "block", reason=reason)
            raise Blocked(reason)

    if _needs_confirmation(tool) and not auto_confirm:
        audit.record(tool, args, "confirm", reason="severity=high")
        raise Blocked(
            f"high-severity tool {tool!r} requires explicit confirmation "
            f"(pass auto_confirm=True to bypass)"
        )

    _record_call(tool)
    try:
        result = TOOLS[tool](**args)
        audit.record(tool, args, "allow")
        return result
    except Exception as e:
        audit.record(tool, args, "allow", reason=f"raised: {e}")
        raise
