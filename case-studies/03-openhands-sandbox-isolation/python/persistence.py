"""persistence.py —— sandbox 元数据 SQLite 持久化 (upgrade #3).

OpenHands 的 ProcessSandboxService 把 sandbox 元信息存在内存全局字典
(process_sandbox_service.py:63 _processes), App Server 重启就丢. 这是已知坑.

本模块演示怎么补这个缺口: SQLite 存 sandbox 元数据, 新进程启动时 reload,
再通过 psutil.Process(pid) 把跑着的 daemon 进程重新接管.

只覆盖 ProcessSandbox. DockerSandbox 的恢复要存 container_id + docker_client.containers.get(),
模式同, 留作衍生题目.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from sandbox import SandboxInfo, SandboxStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sandboxes (
    id              TEXT PRIMARY KEY,
    status          TEXT NOT NULL,
    workspace       TEXT NOT NULL,
    session_api_key TEXT NOT NULL,
    created_at      REAL NOT NULL,
    last_activity_at REAL NOT NULL DEFAULT 0,
    daemon_pid      INTEGER
);
"""


class SandboxRegistry:
    """SQLite 持久化层. 一个 connection 跨线程要加锁."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save(self, info: SandboxInfo) -> None:
        """UPSERT. status / last_activity_at 这种字段会更新."""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO sandboxes (id, status, workspace, session_api_key,
                                       created_at, last_activity_at, daemon_pid)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    last_activity_at = excluded.last_activity_at,
                    daemon_pid = excluded.daemon_pid
                """,
                (
                    info.id,
                    info.status.value,
                    str(info.workspace),
                    info.session_api_key,
                    info.created_at,
                    info.last_activity_at,
                    info.daemon_pid,
                ),
            )
            self._conn.commit()

    def remove(self, sandbox_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM sandboxes WHERE id = ?", (sandbox_id,))
            self._conn.commit()

    def load_all(self) -> list[SandboxInfo]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, status, workspace, session_api_key, "
                "created_at, last_activity_at, daemon_pid FROM sandboxes"
            ).fetchall()
        return [
            SandboxInfo(
                id=r[0],
                status=SandboxStatus(r[1]),
                workspace=Path(r[2]),
                session_api_key=r[3],
                created_at=r[4],
                last_activity_at=r[5],
                daemon_pid=r[6],
            )
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
