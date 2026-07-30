"""callbacks.py —— EventCallbackProcessor ABC + 3 个内置实现.

对标 OpenHands 的 event_callback_models.py:40-48 (ABC) +
set_title_callback_processor.py (业务实现) + event_callback_models.py:51-70 (Logging).
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from events import Event


# ── 结果类型 ──────────────────────────────────────────────────────────
class ResultStatus(str, Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


@dataclass
class CallbackResult:
    """对标 OpenHands EventCallbackResult.

    None 不算 Result —— 它表示 "这次什么都没做, callback 保持 ACTIVE 等下次匹配事件".
    这是 OpenHands 处理 "未就绪" 状态的设计 (SetTitleCallbackProcessor 等 title 没好时返回 None).
    """
    status: ResultStatus
    detail: str = ""
    timestamp: float = field(default_factory=time.time)


# ── 抽象基类 ──────────────────────────────────────────────────────────
class EventCallbackProcessor(ABC):
    """所有 processor 的共同契约.

    返回 None 表示 "未就绪, 下次再试", 返回 Result(SUCCESS) 表示完成,
    Result(ERROR) 表示失败. 没异常抛出 = 失败由 Result.status 体现.
    """

    # 子类应给一个稳定的类型 id, 跨持久化用. (OpenHands 用 Pydantic discriminator.)
    type_id: str = "abstract"

    @abstractmethod
    async def __call__(
        self,
        conversation_id: str,
        event: Event,
    ) -> Optional[CallbackResult]:
        ...


# ── Processor 1: Logging ──────────────────────────────────────────────
class LoggingProcessor(EventCallbackProcessor):
    """对标 OpenHands LoggingCallbackProcessor (event_callback_models.py:51).

    最简单的样板: 把事件打印一行, 永远返回 SUCCESS.
    """
    type_id = "logging"

    def __init__(self, label: str = "LOG") -> None:
        self.label = label

    async def __call__(self, conversation_id: str, event: Event) -> CallbackResult:
        text_preview = json.dumps(event.payload, ensure_ascii=False)[:60]
        print(f"    [{self.label}] {event.kind} on {conversation_id[:8]}: {text_preview}")
        return CallbackResult(status=ResultStatus.SUCCESS)


# ── Processor 2: TitleSetter ───────────────────────────────────────────
class TitleSetterProcessor(EventCallbackProcessor):
    """对标 OpenHands SetTitleCallbackProcessor (set_title_callback_processor.py:80).

    干一件事: 新对话第一条消息后, 调 LLM 生成短标题, 写到 .title 文件.

    复刻关键设计:
      - 只在 'user_message' 上触发 (类似 OpenHands 只在 MessageEvent 触发)
      - 跑完一次自动 disable (set disabled=True), 派发器下次扫描跳过
      - 如果 LLM 没拿到合理 title (返回 None), 保持 ACTIVE 等下次 user_message 重试
    """
    type_id = "title_setter"

    def __init__(self, client, model: str, title_dir: Path) -> None:
        self.client = client
        self.model = model
        self.title_dir = title_dir
        self.disabled = False   # self-DISABLE 状态

    async def __call__(self, conversation_id: str, event: Event) -> Optional[CallbackResult]:
        # 只处理 user_message 类型事件 (OpenHands 也是 type 筛选)
        if event.kind != "user_message":
            return CallbackResult(status=ResultStatus.SUCCESS, detail="not a user_message, skipped")

        # 把 OpenAI 调用包成 sync (我们 demo 用 asyncio.to_thread 走子线程, 避免阻塞 event loop)
        user_text = event.payload.get("text", "")
        if not user_text:
            return None  # 未就绪, 下次再来

        try:
            title = await asyncio.to_thread(
                self._gen_title_sync,
                user_text,
            )
        except Exception as e:
            return CallbackResult(status=ResultStatus.ERROR, detail=f"LLM failure: {e}")

        if not title:
            # 模型没给, 保持 ACTIVE 等下条消息再试 (OpenHands 同样行为)
            return None
        if len(title) > 120:
            # 模型话痨, 截断保留信息
            title = title[:120].rsplit(" ", 1)[0] + "..."

        # 落盘 + self-DISABLE
        self.title_dir.mkdir(parents=True, exist_ok=True)
        (self.title_dir / f"{conversation_id}.title").write_text(title, encoding="utf-8")
        self.disabled = True   # OpenHands 是把 callback.status 改 DISABLED, 等价
        return CallbackResult(status=ResultStatus.SUCCESS, detail=f"title={title!r}")

    def _gen_title_sync(self, first_user_message: str) -> str:
        """同步调 LLM 生成短标题. 用 asyncio.to_thread 包装."""
        # 给个强约束 system + 只让模型出一行
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": (
                    "You generate concise conversation titles. Reply with ONLY the title text, "
                    "no quotes, no explanation, no leading 'Title:', under 60 characters, in the "
                    "input's language. If unsure, still give your best 3-8 word guess."
                )},
                {"role": "user", "content": (
                    f"User started a conversation with:\n{first_user_message}\n\n"
                    "Title:"
                )},
            ],
            temperature=0.2,
            max_tokens=40,  # 强制简短
        )
        raw = (resp.choices[0].message.content or "").strip()
        # 取第一行, 去引号 / 末尾标点
        first_line = raw.splitlines()[0].strip() if raw else ""
        return first_line.strip("'\"`").rstrip(".!?:")


# ── Processor 3: Webhook ──────────────────────────────────────────────
class WebhookProcessor(EventCallbackProcessor):
    """对标 OpenHands 的企业版 SlackV1/GithubV1 等 (模式同).

    真生产: httpx.post(url, json=payload).
    Demo: 写 JSON 文件到 sink_dir 模拟 webhook, 方便观察 + 不依赖外部服务.

    最关键的工程要点: 这是个**会有副作用的 callback** (真生产会 POST 给外部).
    所以这种 callback 务必要做幂等性 —— 但 OpenHands 自己**没做**,
    我们 demo 也没做, 见 BENCHMARK.md 升级清单 #5.
    """
    type_id = "webhook"

    def __init__(self, sink_dir: Path, event_kind_filter: Optional[str] = None) -> None:
        self.sink_dir = sink_dir
        self.event_kind_filter = event_kind_filter
        self.call_count = 0

    async def __call__(self, conversation_id: str, event: Event) -> CallbackResult:
        if self.event_kind_filter and event.kind != self.event_kind_filter:
            return CallbackResult(status=ResultStatus.SUCCESS, detail="filtered out")

        self.sink_dir.mkdir(parents=True, exist_ok=True)
        self.call_count += 1
        fname = f"{int(event.timestamp * 1000)}_{event.event_id[:8]}.json"
        payload = {
            "conversation_id": conversation_id,
            "event_id": event.event_id,
            "event_kind": event.kind,
            "payload": event.payload,
            "delivered_at": time.time(),
        }
        (self.sink_dir / fname).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 真生产里这里会是:
        #   await self.http_client.post(self.url, json=payload, timeout=10)
        return CallbackResult(status=ResultStatus.SUCCESS, detail=f"delivered to {fname}")


# ── Processor 4: 故意失败 (给场景 4 演示失败隔离用) ───────────────────
class FailingProcessor(EventCallbackProcessor):
    """专门 raise Exception 的 processor, 用来演示派发器的容错隔离."""
    type_id = "failing"

    async def __call__(self, conversation_id: str, event: Event):
        raise RuntimeError("intentional failure for demo")
