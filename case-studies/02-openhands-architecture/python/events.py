"""events.py —— append-only 事件存储. 对标 openhands/app_server/event/event_service.py.

OpenHands 的事件存储有 Filesystem / AWS / GoogleCloud 三种实现, 接口都是
"按 conversation_id 读 / 写 / 列举事件". 这里只复刻 Filesystem 版.

每条事件一个 JSON 文件, 命名包含时间戳保证按文件名排序就是按时间排序.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

# 默认存到本 demo 目录下 .events/. 真 OpenHands 用 ~/.openhands/conversations/ 或云存储.
EVENTS_DIR = Path(__file__).parent / ".events"


@dataclass
class Event:
    """对标 OpenHands 的 Event 模型 (简化版).

    字段:
        event_id: UUID, 全局唯一
        conversation_id: 哪个对话
        kind: 事件类型 (user_message / assistant_message / tool_call / tool_result / ...)
        timestamp: unix 时间戳, 排序用
        payload: 业务负载, dict 形式
    """

    kind: str
    conversation_id: str
    payload: dict
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)


def append(event: Event) -> Path:
    """写一条事件到磁盘. 返回事件文件路径.

    文件名: <conversation_dir>/<timestamp>_<event_id>.json
    用时间戳前缀让 sorted(glob('*.json')) 直接得到按时间排序的列表.
    """
    conv_dir = EVENTS_DIR / event.conversation_id
    conv_dir.mkdir(parents=True, exist_ok=True)
    # 时间戳格式化到 6 位小数, 文件名按字典序就是时间序
    fname = f"{event.timestamp:.6f}_{event.event_id}.json"
    path = conv_dir / fname
    path.write_text(
        json.dumps(asdict(event), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def load_all(conversation_id: str) -> list[Event]:
    """加载某个对话的全部事件, 按时间排序.

    任何时候调用都是从磁盘读, 不缓存. (生产可加缓存, 但 demo 要看清流程)
    """
    conv_dir = EVENTS_DIR / conversation_id
    if not conv_dir.exists():
        return []
    events: list[Event] = []
    for fpath in sorted(conv_dir.glob("*.json")):
        data = json.loads(fpath.read_text(encoding="utf-8"))
        events.append(Event(**data))
    return events


def list_conversations() -> list[str]:
    """列出所有有事件记录的 conversation_id."""
    if not EVENTS_DIR.exists():
        return []
    return sorted(d.name for d in EVENTS_DIR.iterdir() if d.is_dir())


def clear(conversation_id: str | None = None) -> None:
    """删除某个对话 (或全部) 的事件. demo 重置用."""
    if conversation_id is None:
        if EVENTS_DIR.exists():
            shutil.rmtree(EVENTS_DIR)
    else:
        conv_dir = EVENTS_DIR / conversation_id
        if conv_dir.exists():
            shutil.rmtree(conv_dir)
