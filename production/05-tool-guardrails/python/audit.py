"""Append-only audit log in JSONL."""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Literal

LOG_FILE = Path(__file__).parent / "logs" / "audit.jsonl"
Decision = Literal["allow", "block", "confirm"]

_lock = threading.Lock()


def record(
    tool: str,
    args: dict,
    decision: Decision,
    reason: str = "",
    actor: str = "agent",
) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "actor": actor,
        "tool": tool,
        "args": args,
        "decision": decision,
        "reason": reason,
    }
    with _lock, LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def tail(n: int = 20) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    with LOG_FILE.open(encoding="utf-8") as f:
        lines = f.readlines()[-n:]
    return [json.loads(line) for line in lines if line.strip()]


def clear() -> None:
    LOG_FILE.unlink(missing_ok=True)
