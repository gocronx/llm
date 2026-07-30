"""docker_sandbox.py —— Docker 后端实现, 跟 ProcessSandbox 共享 SandboxService 抽象.

跟 OpenHands 的对照:
  openhands/app_server/sandbox/docker_sandbox_service.py
    line 10        import docker
    line 360-494   start_sandbox: containers.run(image, init=True, env, ports, volumes, detach)
    line 515-527   pause_sandbox = container.pause()  (内部发 SIGSTOP 给所有进程)
    line 496-513   resume_sandbox = container.unpause()
    line 529-554   delete_sandbox = stop(timeout=10) → remove → 清理 volume

抓的是同一套语义: 一个 SandboxService 抽象 → 多个后端 → main.py 不改一行就能切.

诚实声明 (对标 ANALYSIS.md):
  - 这里没设资源限制 (mem_limit/cpu_quota/pids_limit), 跟 OpenHands 一样 —— 这是已知坑.
  - 网络不过滤, 容器能 curl 外网, 跟 OpenHands 一样.
  - 生产请自己加 mem_limit='2g', cpu_quota=100000, network_mode='internal' 之类.
"""
from __future__ import annotations

import os
import secrets
import shutil
import time
from pathlib import Path
from typing import Optional

from sandbox import SandboxInfo, SandboxService, SandboxStatus

# 默认用社区最广的 python slim 镜像. 真 OpenHands 用自家镜像 (内置 agent server).
# Demo 不需要 agent server, 只需要一个能跑 bash + python 的环境.
DEFAULT_IMAGE = "python:3.11-slim"


# ── 资源限制 (upgrade #2, BENCHMARK 列的高价值生产必备项) ───────────────
# OpenHands docker_sandbox_service.py:463 调 containers.run() 时没设这些, 这是已知坑.
# 一个跑疯的 LLM 可以让一个容器吃满 CPU / 内存 / 把 fd 用光把整机拖垮.
# 这里给个保守默认; 生产按自己产品调整.
RESOURCE_LIMITS = {
    "mem_limit": "512m",      # 内存上限 512MB
    "memswap_limit": "512m",  # 跟 mem_limit 一致 = 禁 swap 滥用
    "cpu_quota": 50000,       # 100ms 周期内最多用 50ms = 0.5 core
    "cpu_period": 100000,     # 配 cpu_quota 用的周期
    "pids_limit": 64,         # 进程总数上限, 防 fork-bomb
}


class DockerSandbox(SandboxService):
    """Docker 后端. 每对话一个独立容器 + 一个 bind-mounted workspace."""

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        image: str = DEFAULT_IMAGE,
    ) -> None:
        # Lazy import: 没装 docker 也不影响 ProcessSandbox 用户.
        try:
            # Optional dependency: ProcessSandbox must work without docker-py.
            import docker  # type: ignore  # noqa: PLC0415
        except ImportError as e:
            raise RuntimeError(
                "DockerSandbox 需要 docker-py: pip install 'docker>=6.0.0'"
            ) from e

        try:
            self._docker = docker.from_env()
            self._docker.ping()
        except Exception as e:
            raise RuntimeError(
                f"Docker daemon 不可达: {e}\n"
                f"提示: 如果用 colima/podman, 先 export DOCKER_HOST=unix:///path/to/socket"
            ) from e

        self.image = image
        self.base_dir = base_dir or Path(__file__).parent / ".sandboxes"
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 用实例属性, 防止跟 ProcessSandbox._registry 串台.
        self._registry: dict[str, dict] = {}

        # 提前确保镜像在本地. 第一次拉可能要几十秒到几分钟.
        self._ensure_image()

    # ── 镜像准备 (OpenHands 也会做) ────────────────────────────────────
    def _ensure_image(self) -> None:
        # Optional dependency: see the guarded import in __init__.
        import docker  # noqa: PLC0415
        try:
            self._docker.images.get(self.image)
        except docker.errors.ImageNotFound:
            print(f"  [Docker] 拉镜像 {self.image} (首次可能要几十秒)...")
            self._docker.images.pull(self.image)
            print(f"  [Docker] 镜像就绪.")

    # ── start ─────────────────────────────────────────────────────────
    def start_sandbox(self) -> SandboxInfo:
        sandbox_id = secrets.token_hex(6)
        workspace = (self.base_dir / sandbox_id).resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        session_key = self._gen_session_key()

        # 心跳 daemon: 同 ProcessSandbox, 让 pause/resume 可视化.
        # 这是容器的主进程 (PID 1), 容器随它生死.
        daemon_script = (
            "import time, pathlib\n"
            "p = pathlib.Path('/workspace/.heartbeat')\n"
            "i = 0\n"
            "while True:\n"
            "    p.write_text(f'tick {i} at {time.time():.3f}\\n')\n"
            "    i += 1\n"
            "    time.sleep(1)\n"
        )

        # 容器以 host 用户 uid/gid 跑, 避免文件回到 host 后变成 root 所有.
        # macOS Docker Desktop / colima 通常会自动处理, 但 Linux 必须显式指定.
        user_spec = f"{os.getuid()}:{os.getgid()}" if os.name == "posix" else None

        info = SandboxInfo(
            id=sandbox_id,
            status=SandboxStatus.STARTING,
            workspace=workspace,
            session_api_key=session_key,
            created_at=time.time(),
        )

        # 对标 OpenHands docker_sandbox_service.py:463
        # 这一行就是 "创建 sandbox = 调 docker API 跑容器".
        container = self._docker.containers.run(
            self.image,
            command=["python", "-c", daemon_script],
            volumes={str(workspace): {"bind": "/workspace", "mode": "rw"}},
            working_dir="/workspace",
            environment={
                # OpenHands 也是这么塞 session key 的 (line 392):
                # 容器内的 agent server 用它做鉴权. Demo 没真起 agent server,
                # 但保留这个 env var 让你看清接口.
                "OH_SESSION_API_KEY": session_key,
            },
            user=user_spec,
            detach=True,
            init=True,            # OpenHands line 463: tini 处理 signal
            # network_mode='none',  # 生产应该启用. demo 不限制保持跟 OpenHands 一致.
            **RESOURCE_LIMITS,    # upgrade #2: mem / cpu / pids 全设上
        )
        info.daemon_pid = None  # daemon 在容器里, host 没 PID

        # 健康检查: 等心跳文件出现. 真 OpenHands 是 HTTP GET /alive 轮询.
        heartbeat = workspace / ".heartbeat"
        for _ in range(100):  # 10 秒上限. 容器启动比进程慢.
            if heartbeat.exists():
                info.status = SandboxStatus.RUNNING
                break
            time.sleep(0.1)
        else:
            info.status = SandboxStatus.ERROR
            try:
                container.kill()
                container.remove()
            except Exception:
                pass

        self._registry[sandbox_id] = {"info": info, "container": container}
        return info

    # ── pause: container.pause() = cgroup freezer (等价 SIGSTOP 所有进程) ──
    def pause_sandbox(self, sandbox_id: str) -> bool:
        state = self._registry.get(sandbox_id)
        if not state or state["info"].status != SandboxStatus.RUNNING:
            return False
        try:
            state["container"].pause()
            state["info"].status = SandboxStatus.PAUSED
            return True
        except Exception:
            state["info"].status = SandboxStatus.ERROR
            return False

    # ── resume: container.unpause() = cgroup unfreezer ────────────────
    def resume_sandbox(self, sandbox_id: str) -> bool:
        state = self._registry.get(sandbox_id)
        if not state or state["info"].status != SandboxStatus.PAUSED:
            return False
        try:
            state["container"].unpause()
            state["info"].status = SandboxStatus.RUNNING
            return True
        except Exception:
            state["info"].status = SandboxStatus.ERROR
            return False

    # ── delete: stop → remove → 清理 workspace ────────────────────────
    def delete_sandbox(self, sandbox_id: str) -> bool:
        state = self._registry.get(sandbox_id)
        if not state:
            return False
        container = state["container"]
        try:
            if state["info"].status == SandboxStatus.PAUSED:
                container.unpause()
            container.stop(timeout=3)  # OpenHands 用 timeout=10
        except Exception:
            try:
                container.kill()
            except Exception:
                pass
        try:
            container.remove(force=True)
        except Exception:
            pass
        if state["info"].workspace.exists():
            shutil.rmtree(state["info"].workspace, ignore_errors=True)
        del self._registry[sandbox_id]
        return True

    # ── get ───────────────────────────────────────────────────────────
    def get_sandbox(self, sandbox_id: str) -> Optional[SandboxInfo]:
        state = self._registry.get(sandbox_id)
        return state["info"] if state else None

    # ── 给基类 sweeper 用 ──────────────────────────────────────────────
    def _iter_infos(self) -> list[tuple[str, SandboxInfo]]:
        return [(sid, state["info"]) for sid, state in self._registry.items()]

    # ── exec: container.exec_run() 在容器内跑命令 ──────────────────────
    def exec_in_sandbox(
        self,
        sandbox_id: str,
        session_api_key: str,
        command: str,
    ) -> tuple[int, str, str]:
        state = self._registry.get(sandbox_id)
        if not state:
            return (127, "", f"sandbox {sandbox_id} not found")
        if not self._check_session_key(session_api_key, state["info"].session_api_key):
            return (1, "", "invalid session_api_key")
        if state["info"].status != SandboxStatus.RUNNING:
            return (1, "", f"sandbox status is {state['info'].status.value}, must be RUNNING")

        # upgrade #5: idle sweeper 需要这个时间戳
        state["info"].last_activity_at = time.time()

        # 真 OpenHands: App Server POST /api/v1/events 给容器里的 Agent Server,
        # Agent Server 再 subprocess.Popen 跑 bash. 中间多一层 HTTP.
        # Demo 直接走 docker exec, 业务效果等价.
        result = state["container"].exec_run(
            ["bash", "-c", command],
            workdir="/workspace",
            demux=True,  # 分开 stdout / stderr
        )
        stdout_b, stderr_b = result.output if result.output else (None, None)
        stdout = stdout_b.decode("utf-8", errors="replace") if stdout_b else ""
        stderr = stderr_b.decode("utf-8", errors="replace") if stderr_b else ""
        return (result.exit_code, stdout, stderr)
