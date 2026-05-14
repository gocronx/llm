"""Raw tool implementations. The guardrail layer in guardrails.py wraps these."""

import subprocess
from pathlib import Path
from typing import Literal

import requests

WORKSPACE = Path(__file__).parent / "data"
Severity = Literal["low", "medium", "high"]


def read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_file(path: str, content: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} bytes to {p}"


def delete_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    if p.is_dir():
        # Deliberately non-recursive; guardrails should block dangerous recursive removals.
        p.rmdir()
    else:
        p.unlink()
    return f"deleted {p}"


def run_shell(cmd: str) -> str:
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=10,
    )
    return result.stdout or result.stderr


def http_get(url: str) -> str:
    resp = requests.get(url, timeout=5)
    return f"HTTP {resp.status_code}: {resp.text[:200]}"


TOOLS = {
    "read_file":   read_file,
    "write_file":  write_file,
    "delete_file": delete_file,
    "run_shell":   run_shell,
    "http_get":    http_get,
}

SEVERITY: dict[str, Severity] = {
    "read_file":   "low",
    "http_get":    "low",
    "write_file":  "medium",
    "delete_file": "high",
    "run_shell":   "high",
}
