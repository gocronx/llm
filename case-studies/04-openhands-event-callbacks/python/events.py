"""events.py —— 最小事件存储, 给本 demo 用. 不复用 case 02 的 events.py
是为了 case 自包含, 但概念一致.

对标 OpenHands openhands/app_server/event/event_service.py 的 FilesystemEventService.
"""
from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

EVENTS_DIR = Path(__file__).parent / ".events"


@dataclass
class Event:
    """对标 OpenHands SDK 的 Event 模型.

    kind: 事件类型字符串 (MessageEvent / ToolResultEvent / ...).
    OpenHands 用 EventKind = Literal[tuple(子类名)] 动态生成, 本 demo 用字符串简化.
    """
    kind: str
    conversation_id: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)


def append(event: Event) -> Path:
    """写盘. 文件名带时间戳, 排序就是时间序."""
    conv_dir = EVENTS_DIR / event.conversation_id
    conv_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{event.timestamp:.6f}_{event.event_id}.json"
    path = conv_dir / fname
    path.write_text(json.dumps(asdict(event), ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


def load_all(conversation_id: str) -> list[Event]:
    conv_dir = EVENTS_DIR / conversation_id
    if not conv_dir.exists():
        return []
    out: list[Event] = []
    for fpath in sorted(conv_dir.glob("*.json")):
        out.append(Event(**json.loads(fpath.read_text(encoding="utf-8"))))
    return out


def clear() -> None:
    if EVENTS_DIR.exists():
        shutil.rmtree(EVENTS_DIR)
