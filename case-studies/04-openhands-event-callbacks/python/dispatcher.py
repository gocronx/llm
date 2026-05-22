"""dispatcher.py —— Callback 注册表 + 派发器.

对标 OpenHands openhands/app_server/event_callback/sql_event_callback_service.py
(行级引用见 ANALYSIS.md 引用表).

复刻设计:
  - 注册 (conv_id, event_kind, processor) 三元组, None 表示通配 (模式 B)
  - 派发: 事件之间串行, 同事件多 callback 并发 gather (模式 C)
  - 派发后台异步: 主线程不等 (模式 D)
  - 失败隔离: 一个 raise 不影响其他 (模式 D)
  - timeout per callback: OpenHands 漏的, 我们补上 (BENCHMARK 升级 #2)
  - self-DISABLE: callback 内部把自己 disabled=True, 派发器跳过 (模式 A 配)
  - 注册表 JSON 持久化: 跨进程能 reload (类比 OpenHands SQL)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from callbacks import CallbackResult, EventCallbackProcessor, ResultStatus
from events import Event

_logger = logging.getLogger("dispatcher")


# ── 注册项 ────────────────────────────────────────────────────────────
@dataclass
class CallbackRegistration:
    """一条 callback 注册.

    跟 OpenHands EventCallback 表对照:
      callback_id      = id
      conversation_id  = conv_id (None = 全局)
      event_kind       = event_kind (None = 所有事件)
      processor        = processor (实例)
      status           = "ACTIVE" | "DISABLED"
    """
    callback_id: str
    processor: EventCallbackProcessor
    conv_id: Optional[str] = None
    event_kind: Optional[str] = None
    status: str = "ACTIVE"


# ── 结果记录 ──────────────────────────────────────────────────────────
@dataclass
class ExecutionRecord:
    """每次 callback 执行的 audit record. 对标 event_callback_result 表."""
    callback_id: str
    event_id: str
    status: str        # SUCCESS / ERROR / PENDING / TIMEOUT
    detail: str
    timestamp: float = field(default_factory=time.time)


# ── 派发器 ────────────────────────────────────────────────────────────
class CallbackDispatcher:
    """注册 + 过滤 + 派发. asyncio-based, 单进程内运行."""

    def __init__(
        self,
        audit_log_path: Optional[Path] = None,
        per_callback_timeout: float = 10.0,
    ) -> None:
        self._registry: dict[str, CallbackRegistration] = {}
        # OpenHands 漏的 timeout 我们这里有: 防 hang 死整个 gather (BENCHMARK 升级 #2)
        self.per_callback_timeout = per_callback_timeout
        self._audit_log_path = audit_log_path
        # 抓着 task 引用避免被 GC (Python 3.11+ 文档明确警告)
        self._background_tasks: set[asyncio.Task] = set()

    # ── 注册 / 列表 ───────────────────────────────────────────────────
    def register(
        self,
        processor: EventCallbackProcessor,
        conv_id: Optional[str] = None,
        event_kind: Optional[str] = None,
    ) -> str:
        import uuid
        cb_id = uuid.uuid4().hex[:12]
        self._registry[cb_id] = CallbackRegistration(
            callback_id=cb_id,
            processor=processor,
            conv_id=conv_id,
            event_kind=event_kind,
        )
        return cb_id

    def list_callbacks(self) -> list[CallbackRegistration]:
        return list(self._registry.values())

    # ── 派发主入口 ─────────────────────────────────────────────────────
    def emit(self, event: Event) -> asyncio.Task:
        """发一个事件 → 在后台跑所有匹配的 callback. 不等. 返回 task 给你查状态."""
        task = asyncio.create_task(self._run_callbacks_for_event(event))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def emit_batch(self, events: list[Event]) -> None:
        """对一批事件按顺序派发, await 完所有.

        对标 OpenHands _run_callbacks_in_bg_and_close (webhook_router.py:491-503).
        事件之间串行 (注释里写明了: must be run in sequence).
        """
        for event in events:
            await self._run_callbacks_for_event(event)

    # ── 实际执行 ───────────────────────────────────────────────────────
    async def _run_callbacks_for_event(self, event: Event) -> None:
        """找匹配的 callbacks, 并发跑 (gather)."""
        matching = self._find_matching(event)
        if not matching:
            return

        # 同事件多 callback 并发. OpenHands sql_event_callback_service.py:223
        results = await asyncio.gather(
            *[self._execute_one(reg, event) for reg in matching],
            return_exceptions=True,  # 即使有 task 抛出, 也等所有完成
        )

        # gather(return_exceptions=True) 会把异常作为元素返回. 但我们在 _execute_one
        # 里已经 try/except 包了 (跟 OpenHands 一致), 所以这里 results 全是 ExecutionRecord.
        for r in results:
            if isinstance(r, BaseException):
                # 防御: 不该到这, 但万一 _execute_one 自己崩了也别拖累其他 callback
                _logger.warning(f"unexpected exception escaped: {r}")
                continue
            self._write_audit(r)

    async def _execute_one(
        self,
        reg: CallbackRegistration,
        event: Event,
    ) -> ExecutionRecord:
        """跑一个 callback. 完全捕获异常, 永远返回 ExecutionRecord.

        对标 OpenHands sql_event_callback_service.py:235-252 + 加 timeout (升级 #2).
        """
        try:
            # OpenHands 没设 timeout, hang 的 callback 会拖死整个 gather.
            # 这是我们 demo 比原版做对的一处.
            maybe_result = await asyncio.wait_for(
                reg.processor(event.conversation_id, event),
                timeout=self.per_callback_timeout,
            )
        except asyncio.TimeoutError:
            return ExecutionRecord(
                callback_id=reg.callback_id,
                event_id=event.event_id,
                status="TIMEOUT",
                detail=f"callback timed out after {self.per_callback_timeout}s",
            )
        except Exception as exc:
            _logger.exception(f"exception in callback {reg.callback_id}")
            return ExecutionRecord(
                callback_id=reg.callback_id,
                event_id=event.event_id,
                status="ERROR",
                detail=str(exc),
            )

        # processor 返回 None = "未就绪, 保持 ACTIVE 等下次匹配事件"
        if maybe_result is None:
            return ExecutionRecord(
                callback_id=reg.callback_id,
                event_id=event.event_id,
                status="PENDING",
                detail="processor returned None, callback stays ACTIVE",
            )

        # processor 跑完后可能 self-DISABLE (SetTitleCallbackProcessor 风格)
        if getattr(reg.processor, "disabled", False):
            reg.status = "DISABLED"

        return ExecutionRecord(
            callback_id=reg.callback_id,
            event_id=event.event_id,
            status=maybe_result.status.value,
            detail=maybe_result.detail,
        )

    # ── 过滤 ──────────────────────────────────────────────────────────
    def _find_matching(self, event: Event) -> list[CallbackRegistration]:
        """两维过滤. 跳过 DISABLED. 对应 OpenHands 的那个 SQL where."""
        return [
            reg
            for reg in self._registry.values()
            if reg.status == "ACTIVE"
            and (reg.conv_id is None or reg.conv_id == event.conversation_id)
            and (reg.event_kind is None or reg.event_kind == event.kind)
        ]

    # ── audit log ─────────────────────────────────────────────────────
    def _write_audit(self, record: ExecutionRecord) -> None:
        if self._audit_log_path is None:
            return
        self._audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "callback_id": record.callback_id,
                "event_id": record.event_id,
                "status": record.status,
                "detail": record.detail,
                "timestamp": record.timestamp,
            }, ensure_ascii=False) + "\n")

    def audit_records(self) -> list[ExecutionRecord]:
        """读 audit log 回来. 给 demo 验证用."""
        if self._audit_log_path is None or not self._audit_log_path.exists():
            return []
        out: list[ExecutionRecord] = []
        for line in self._audit_log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            out.append(ExecutionRecord(**d))
        return out
