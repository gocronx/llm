"""JSON-file state store: thread-safe within a process, atomic via tmp+rename."""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

STATE_FILE = Path(__file__).parent / "data" / "state.json"
MAX_EVENTS = 200

_lock = threading.Lock()


def _load() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def get(key: str, default: Any = None) -> Any:
    with _lock:
        return _load().get(key, default)


def set_(key: str, value: Any) -> None:
    with _lock:
        data = _load()
        data[key] = value
        _save(data)


def append_event(event: dict) -> None:
    with _lock:
        data = _load()
        events = data.get("events", [])
        events.append({"ts": datetime.now().isoformat(timespec="seconds"), **event})
        data["events"] = events[-MAX_EVENTS:]
        _save(data)


def get_events_since(seconds_ago: int) -> list[dict]:
    cutoff = datetime.now().timestamp() - seconds_ago
    with _lock:
        events = _load().get("events", [])
    out = []
    for e in events:
        try:
            ts = datetime.fromisoformat(e["ts"]).timestamp()
        except (KeyError, ValueError):
            continue
        if ts >= cutoff:
            out.append(e)
    return out
