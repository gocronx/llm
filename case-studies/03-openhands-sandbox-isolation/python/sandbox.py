"""sandbox.py —— 复刻 OpenHands ProcessSandbox 的最小版本.

跟 OpenHands 的对照:
  - SandboxService (ABC)        → openhands/app_server/sandbox/sandbox_service.py:29
  - SandboxInfo / SandboxStatus → openhands/app_server/sandbox/sandbox_models.py:9-56
  - ProcessSandboxService       → openhands/app_server/sandbox/process_sandbox_service.py:67-462

诚实声明: ProcessSandbox 不是真正的 sandbox, 只是 silo —— 没 namespace 隔离, 没 chroot,
只是独立的工作目录 + 独立的子进程. Agent 完全能 cat /etc/passwd. 生产请用 Docker.
本 demo 沿用这个设计是为了让任何机器都能跑, 不依赖 docker.

砍掉的部分:
  - asyncio (用同步, 看清流程)
  - 数据库持久化 (内存字典, 重启丢)
  - HTTP 健康检查 (用 file-based 心跳代替)
  - Docker / Remote 后端 (只保留抽象基类 + ProcessSandbox)
"""
from __future__ import annotations

import hmac
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import psutil

# ── 命令安全检查 (upgrade #6, 仅 ProcessSandbox 用; Docker 不需要) ──────
# 诚实声明: 这是 best-effort 字符串匹配, NOT 真正的安全沙盒.
# 真实的 LLM 能通过 base64 / 变量 / shell 替换绕过它. 这是 fig leaf, 不是城墙.
# 真要安全请用 Docker 后端 (有 namespace 隔离).
# 之所以加这一层: ProcessSandbox 暴露给 demo 用户时, 防一下最显眼的事故.
_DENIED_PATTERNS = [
    r'/etc/',         # 系统配置
    r'/usr/',         # 系统二进制
    r'/var/',         # 系统状态
    r'/sys/',         # 内核接口
    r'/proc/',        # 进程信息
    r'/root/',        # root 家目录
    r'~[/\s]',        # 用户家目录
    r'\$HOME',        # 同上
    r'\.\./',         # 路径回溯
]
_DENIED_RE = re.compile('|'.join(_DENIED_PATTERNS))


def _command_looks_safe(cmd: str) -> tuple[bool, str]:
    """返回 (ok, 拒绝原因). 命中任何危险 pattern 就拒.

    NOT 完整安全检查. 是字符串黑名单兜底, 真正安全要靠 Docker 后端.
    """
    m = _DENIED_RE.search(cmd)
    if m:
        return (False, f"command matched denied pattern: {m.group(0)!r}. "
                       f"ProcessSandbox is not a real sandbox; use Docker backend for unsafe commands.")
    return (True, "")


# ── 数据模型 (对标 sandbox_models.py) ─────────────────────────────────
class SandboxStatus(str, Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"
    MISSING = "MISSING"


@dataclass
class SandboxInfo:
    """对标 SandboxInfo dataclass.

    每个 sandbox 一个 session_api_key, 这是访问 sandbox 的必带凭证.
    workspace 是隔离的工作目录, agent 的所有文件操作都在这里发生.
    last_activity_at 给 idle-timeout sweeper 用 (upgrade #5).
    """
    id: str
    status: SandboxStatus
    workspace: Path
    session_api_key: str
    created_at: float
    last_activity_at: float = 0.0          # 最近一次 exec / pause / resume 的时间
    daemon_pid: Optional[int] = None       # 长寿 daemon 进程, pause/resume 的对象


# ── 抽象基类 (对标 SandboxService) ────────────────────────────────────
class SandboxService(ABC):
    """所有 sandbox 后端都实现这个契约.

    业务代码只跟这个抽象类打交道, 不知道底层是 process / docker / k8s.
    切后端 = 换实现, 业务代码零改动.
    """

    @abstractmethod
    def start_sandbox(self) -> SandboxInfo: ...

    @abstractmethod
    def pause_sandbox(self, sandbox_id: str) -> bool: ...

    @abstractmethod
    def resume_sandbox(self, sandbox_id: str) -> bool: ...

    @abstractmethod
    def delete_sandbox(self, sandbox_id: str) -> bool: ...

    @abstractmethod
    def get_sandbox(self, sandbox_id: str) -> Optional[SandboxInfo]: ...

    @abstractmethod
    def exec_in_sandbox(
        self,
        sandbox_id: str,
        session_api_key: str,
        command: str,
    ) -> tuple[int, str, str]:
        """在 sandbox 里跑一条 shell 命令.

        生产里 OpenHands 是: App Server → POST {agent_server_url}/api/v1/events
                          → Agent Server → subprocess.Popen 在 sandbox 内
        Demo 简化成: 直接调本方法, 但仍走 session_api_key 鉴权.

        返回 (returncode, stdout, stderr).
        """
        ...

    @abstractmethod
    def _iter_infos(self) -> list[tuple[str, "SandboxInfo"]]:
        """给基类的 sweeper / 重启复活 等机制用. 返回 (id, info) 列表."""
        ...

    # ── upgrade #5: idle-timeout sweeper, 后端通用 ─────────────────────
    # 真 OpenHands 类似机制在 enterprise/ 里, OSS 看不到完整版.
    # 后台线程扫描, 把闲置太久的 RUNNING sandbox 自动 pause, 省资源.
    def start_idle_sweeper(
        self,
        idle_timeout_seconds: float,
        sweep_interval_seconds: float = 2.0,
    ):
        """启动后台 sweeper. 返回 stop_event, 调用方 stop_event.set() 终止."""
        stop_event = threading.Event()

        def sweep() -> None:
            while not stop_event.is_set():
                now = time.time()
                for sid, info in self._iter_infos():
                    if info.status != SandboxStatus.RUNNING:
                        continue
                    last = max(info.last_activity_at, info.created_at)
                    if now - last >= idle_timeout_seconds:
                        try:
                            self.pause_sandbox(sid)
                        except Exception:
                            pass  # best effort
                stop_event.wait(sweep_interval_seconds)

        threading.Thread(target=sweep, daemon=True, name="idle-sweeper").start()
        return stop_event

    # ── 工具方法, 给所有后端用 ────────────────────────────────────────
    @staticmethod
    def _gen_session_key() -> str:
        """对标 OpenHands base62 96-bit. Demo 用 secrets.token_urlsafe."""
        return secrets.token_urlsafe(16)  # 128 bit, 简化

    @staticmethod
    def _check_session_key(provided: str, stored: str) -> bool:
        """timing-safe 比较."""
        return hmac.compare_digest(provided.encode(), stored.encode())


# ── ProcessSandbox 实现 ────────────────────────────────────────────────
class ProcessSandbox(SandboxService):
    """对标 ProcessSandboxService.

    每个 sandbox =
      - 一个独立 working directory (tempdir)
      - 一个长寿 daemon 进程 (写心跳文件, 用来 pause/resume 演示)
      - 一个独立 session_api_key
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        db_path: Optional[Path] = None,
    ) -> None:
        self.base_dir = base_dir or Path(__file__).parent / ".sandboxes"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # 实例级注册表. 对标 OpenHands 的 _processes dict (line 63).
        # 默认重启丢; 传 db_path 启用 SQLite 持久化 (upgrade #3).
        self._registry: dict[str, "_SandboxState"] = {}

        # upgrade #3: 可选持久化
        self._db = None
        if db_path is not None:
            # Circular dependency: persistence imports SandboxInfo from this module.
            from persistence import SandboxRegistry  # noqa: PLC0415
            self._db = SandboxRegistry(db_path)
            self._reload_from_db()

    def _reload_from_db(self) -> None:
        """从 DB 把之前记录的 sandbox 拉回内存. 用 psutil 验证进程是否还活着."""
        if self._db is None:
            return
        for info in self._db.load_all():
            alive = False
            if info.daemon_pid is not None:
                try:
                    p = psutil.Process(info.daemon_pid)
                    # 还要确认这个 pid 是 *我们的* daemon 不是别人复用了同号
                    # 简化: 看进程命令行里有没有我们的 workspace 路径
                    cmdline = " ".join(p.cmdline())
                    if str(info.workspace) in cmdline:
                        alive = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            if alive:
                # daemon 还在跑, 重新接管. 没 Popen 句柄但能用 psutil 操作.
                self._registry[info.id] = _SandboxState(info=info, daemon=None)
            else:
                # daemon 死了 (机器重启 / 被 kill / 等等)
                info.status = SandboxStatus.MISSING
                self._db.save(info)
                self._registry[info.id] = _SandboxState(info=info, daemon=None)

    # ── start ─────────────────────────────────────────────────────────
    def start_sandbox(self) -> SandboxInfo:
        sandbox_id = secrets.token_hex(6)
        workspace = self.base_dir / sandbox_id
        workspace.mkdir(parents=True, exist_ok=True)
        session_key = self._gen_session_key()

        info = SandboxInfo(
            id=sandbox_id,
            status=SandboxStatus.STARTING,
            workspace=workspace,
            session_api_key=session_key,
            created_at=time.time(),
        )

        # 起一个长寿 daemon: 每秒写一次心跳文件.
        # 这是 OpenHands 里 "python -m openhands.agent_server" 的占位:
        # 真的 agent server 也是长寿进程, 监听端口, 暴露 /alive.
        # 这里用心跳文件让 pause/resume 的效果可以 "看见".
        heartbeat = workspace / ".heartbeat"
        daemon_cmd = [
            sys.executable, "-c",
            f"import time, pathlib;\n"
            f"p = pathlib.Path({str(heartbeat)!r});\n"
            f"i = 0\n"
            f"while True:\n"
            f"    p.write_text(f'tick {{i}} at {{time.time():.3f}}\\n')\n"
            f"    i += 1\n"
            f"    time.sleep(1)\n"
        ]
        log_file = workspace / ".sandbox-daemon.log"
        # 对标 OpenHands process_sandbox_service.py:139-143:
        # 把 stdout/stderr 重定向到文件避免 pipe 死锁.
        proc = subprocess.Popen(
            daemon_cmd,
            cwd=str(workspace),
            stdout=open(log_file, "w"),
            stderr=subprocess.STDOUT,
        )
        info.daemon_pid = proc.pid

        # 等心跳文件出现 (相当于健康检查). 真 OpenHands 是轮询 HTTP /alive.
        for _ in range(50):  # 5 秒上限
            if heartbeat.exists():
                info.status = SandboxStatus.RUNNING
                break
            time.sleep(0.1)
        else:
            info.status = SandboxStatus.ERROR
            proc.terminate()

        self._registry[sandbox_id] = _SandboxState(info=info, daemon=proc)
        if self._db:
            self._db.save(info)
        return info

    # ── pause / resume (psutil SIGSTOP / SIGCONT) ──────────────────────
    def pause_sandbox(self, sandbox_id: str) -> bool:
        state = self._registry.get(sandbox_id)
        if not state or state.info.status != SandboxStatus.RUNNING:
            return False
        if state.info.daemon_pid is None:
            return False
        try:
            psutil.Process(state.info.daemon_pid).suspend()
            state.info.status = SandboxStatus.PAUSED
            if self._db:
                self._db.save(state.info)
            return True
        except psutil.NoSuchProcess:
            state.info.status = SandboxStatus.MISSING
            if self._db:
                self._db.save(state.info)
            return False

    def resume_sandbox(self, sandbox_id: str) -> bool:
        state = self._registry.get(sandbox_id)
        if not state or state.info.status != SandboxStatus.PAUSED:
            return False
        if state.info.daemon_pid is None:
            return False
        try:
            psutil.Process(state.info.daemon_pid).resume()
            state.info.status = SandboxStatus.RUNNING
            if self._db:
                self._db.save(state.info)
            return True
        except psutil.NoSuchProcess:
            state.info.status = SandboxStatus.MISSING
            if self._db:
                self._db.save(state.info)
            return False

    # ── delete: terminate → kill timeout → cleanup ─────────────────────
    def delete_sandbox(self, sandbox_id: str) -> bool:
        state = self._registry.get(sandbox_id)
        if not state:
            return False
        if state.info.daemon_pid is not None:
            try:
                p = psutil.Process(state.info.daemon_pid)
                # paused 进程不能被 SIGTERM 收到, 先 resume 再终止
                if state.info.status == SandboxStatus.PAUSED:
                    p.resume()
                p.terminate()
                try:
                    p.wait(timeout=3)
                except psutil.TimeoutExpired:
                    p.kill()
            except psutil.NoSuchProcess:
                pass  # 进程已经没了, 直接清目录

        if state.info.workspace.exists():
            shutil.rmtree(state.info.workspace, ignore_errors=True)
        del self._registry[sandbox_id]
        if self._db:
            self._db.remove(sandbox_id)
        return True

    # ── get ───────────────────────────────────────────────────────────
    def get_sandbox(self, sandbox_id: str) -> Optional[SandboxInfo]:
        state = self._registry.get(sandbox_id)
        return state.info if state else None

    # ── exec: 在 sandbox 内跑命令 ──────────────────────────────────────
    def exec_in_sandbox(
        self,
        sandbox_id: str,
        session_api_key: str,
        command: str,
    ) -> tuple[int, str, str]:
        state = self._registry.get(sandbox_id)
        if not state:
            return (127, "", f"sandbox {sandbox_id} not found")

        # 鉴权 (对标 X-Session-API-Key 头)
        if not self._check_session_key(session_api_key, state.info.session_api_key):
            return (1, "", "invalid session_api_key")

        if state.info.status != SandboxStatus.RUNNING:
            return (1, "", f"sandbox status is {state.info.status.value}, must be RUNNING")

        # upgrade #6: best-effort 路径黑名单. 防 LLM 顺手 cat /etc/passwd 这类事故.
        # 不是安全保证 — Docker 后端才是.
        ok, reason = _command_looks_safe(command)
        if not ok:
            return (126, "", f"refused: {reason}")

        # upgrade #5: 标记活动时间, 给 idle sweeper 用
        state.info.last_activity_at = time.time()

        # 在 sandbox workspace 里跑.
        result = subprocess.run(
            ["bash", "-c", command],
            cwd=str(state.info.workspace),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return (result.returncode, result.stdout, result.stderr)

    # ── 给基类 sweeper 用 ──────────────────────────────────────────────
    def _iter_infos(self) -> list[tuple[str, SandboxInfo]]:
        return [(sid, state.info) for sid, state in self._registry.items()]


# ── 内部状态结构 ──────────────────────────────────────────────────────
@dataclass
class _SandboxState:
    """SandboxInfo + Popen 句柄. 进程重启后 reload 出来的 daemon=None
    (用 info.daemon_pid + psutil 仍能操作)."""
    info: SandboxInfo
    daemon: Optional[subprocess.Popen] = None
