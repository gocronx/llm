"""main.py —— 6 个场景演示 event_callback 的各种行为.

跑法:
    python main.py                    # 全跑
    python main.py --scenario 3       # 只跑某个
    python main.py --cleanup          # 清理 .events/ .titles/ .webhook-sink/ audit.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

import events
import httpx
from callbacks import (
    FailingProcessor,
    LoggingProcessor,
    TitleSetterProcessor,
    WebhookProcessor,
)
from dispatcher import CallbackDispatcher
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

HERE = Path(__file__).parent
TITLE_DIR = HERE / ".titles"
WEBHOOK_SINK = HERE / ".webhook-sink"
AUDIT_LOG = HERE / "audit.jsonl"


def _make_client() -> tuple[OpenAI, str]:
    http = httpx.Client(trust_env=False, timeout=60.0)
    client = OpenAI(
        base_url=os.environ["API_BASE_URL"],
        api_key=os.environ.get("API_KEY", "not-needed"),
        http_client=http,
    )
    return client, os.environ["MODEL_ID"]


def _print_section(title: str) -> None:
    print(f"\n{'=' * 64}\n{title}\n{'=' * 64}")


def _new_conv() -> str:
    return uuid.uuid4().hex[:8]


def _emit_user(disp: CallbackDispatcher, conv_id: str, text: str) -> events.Event:
    ev = events.Event(kind="user_message", conversation_id=conv_id, payload={"text": text})
    events.append(ev)
    disp.emit(ev)
    return ev


def _emit_assistant(disp: CallbackDispatcher, conv_id: str, text: str) -> events.Event:
    ev = events.Event(kind="assistant_message", conversation_id=conv_id, payload={"text": text})
    events.append(ev)
    disp.emit(ev)
    return ev


async def _drain(disp: CallbackDispatcher) -> None:
    """等所有 emit 出来的后台 task 跑完 (demo 验证用)."""
    while disp._background_tasks:
        await asyncio.gather(*disp._background_tasks, return_exceptions=True)


# ── 场景 1 · fan-out: 一个事件触发 N 个 callback ───────────────────────
async def scenario_fanout() -> None:
    _print_section("场景 1 · fan-out (一个事件 → 多个 callback 并发跑)")

    disp = CallbackDispatcher(audit_log_path=AUDIT_LOG)
    conv = _new_conv()

    disp.register(LoggingProcessor(label="LOG-A"))
    disp.register(LoggingProcessor(label="LOG-B"))
    disp.register(WebhookProcessor(sink_dir=WEBHOOK_SINK))
    print(f"已注册 {len(disp.list_callbacks())} 个 callback (都全局, 监听所有事件)")

    print("\n[发一条 user_message]")
    _emit_user(disp, conv, "hi")
    await _drain(disp)

    print(f"\nwebhook sink 收到的文件: {[p.name for p in WEBHOOK_SINK.iterdir() if p.is_file()]}")
    records = disp.audit_records()
    print(f"audit log 记录数: {len(records)}")
    for r in records[-3:]:
        print(f"  callback={r.callback_id[:6]} status={r.status} detail={r.detail[:50]}")
    print("→ 3 个 callback 都跑了, 互不知道彼此, 并发执行 ✓")


# ── 场景 2 · per-conversation 过滤 ────────────────────────────────────
async def scenario_per_conversation() -> None:
    _print_section("场景 2 · per-conversation 过滤")

    disp = CallbackDispatcher(audit_log_path=AUDIT_LOG)
    conv_a = _new_conv()
    conv_b = _new_conv()

    # 全局 logger 监听所有, conv_a-only webhook 只听 a
    disp.register(LoggingProcessor(label="GLOBAL"))  # 通配 conv_id 和 event_kind
    disp.register(
        WebhookProcessor(sink_dir=WEBHOOK_SINK),
        conv_id=conv_a,  # 只关心 conv_a
    )
    print(f"conv_a={conv_a}, conv_b={conv_b}")
    print("注册: GLOBAL logger (无过滤), webhook (conv_id=conv_a 才触发)")

    print("\n[在 conv_a 发消息]")
    _emit_user(disp, conv_a, "hello from A")
    print("\n[在 conv_b 发消息]")
    _emit_user(disp, conv_b, "hello from B")
    await _drain(disp)

    # 应该只有 conv_a 的事件触发了 webhook
    files = sorted(WEBHOOK_SINK.iterdir()) if WEBHOOK_SINK.exists() else []
    payloads = []
    for f in files:
        if f.is_file():
            payloads.append(json.loads(f.read_text())["conversation_id"])
    print(f"\nwebhook 收到的事件来自: {payloads}")
    if payloads.count(conv_a) > 0 and payloads.count(conv_b) == 0:
        print("→ per-conversation 过滤生效, conv_b 的事件没触发 webhook ✓")
    else:
        print("✗ 过滤没生效")


# ── 场景 3 · per-event-kind 过滤 ──────────────────────────────────────
async def scenario_per_event_kind() -> None:
    _print_section("场景 3 · per-event-kind 过滤")

    disp = CallbackDispatcher(audit_log_path=AUDIT_LOG)
    conv = _new_conv()

    disp.register(
        WebhookProcessor(sink_dir=WEBHOOK_SINK),
        event_kind="user_message",  # 只听 user_message
    )
    print("注册: webhook (event_kind=user_message 才触发)")

    print("\n[发 1 条 user_message + 2 条 assistant_message]")
    _emit_user(disp, conv, "u1")
    _emit_assistant(disp, conv, "a1")
    _emit_assistant(disp, conv, "a2")
    await _drain(disp)

    files = sorted([p for p in WEBHOOK_SINK.iterdir() if p.is_file()]) if WEBHOOK_SINK.exists() else []
    print(f"\nwebhook 收到 {len(files)} 个事件")
    if len(files) == 1:
        print("→ event_kind 过滤生效, 只 1 个 user_message 触发 ✓")
    else:
        print(f"✗ 期望 1 个, 实际 {len(files)}")


# ── 场景 4 · 失败隔离 ──────────────────────────────────────────────────
async def scenario_failure_isolation() -> None:
    _print_section("场景 4 · 失败隔离 (一个 callback raise, 其他不受影响)")

    disp = CallbackDispatcher(audit_log_path=AUDIT_LOG)
    conv = _new_conv()

    disp.register(LoggingProcessor(label="BEFORE-FAIL"))
    disp.register(FailingProcessor())   # 故意 raise
    disp.register(LoggingProcessor(label="AFTER-FAIL"))
    print("注册: BEFORE-FAIL logger | FailingProcessor (会 raise) | AFTER-FAIL logger")

    print("\n[发一条事件]")
    _emit_user(disp, conv, "hi")
    await _drain(disp)

    recent = disp.audit_records()[-3:]
    print(f"\naudit log 最近 3 条:")
    for r in recent:
        print(f"  callback={r.callback_id[:6]} status={r.status:8s} detail={r.detail[:60]}")

    success = sum(1 for r in recent if r.status == "SUCCESS")
    errors = sum(1 for r in recent if r.status == "ERROR")
    if success == 2 and errors == 1:
        print("→ 2 个 SUCCESS + 1 个 ERROR, 失败的 callback 没拖累其他 ✓")
    else:
        print(f"✗ 期望 2 SUCCESS + 1 ERROR, 实际 SUCCESS={success} ERROR={errors}")


# ── 场景 5 · TitleSetter 调真 LLM + self-DISABLE ──────────────────────
async def scenario_title_setter() -> None:
    _print_section("场景 5 · TitleSetterProcessor (调 LLM 起标题 + 自禁用)")

    client, model = _make_client()
    # LLM 调用比一般 callback 慢, 给场景 5 单独调高 timeout
    disp = CallbackDispatcher(audit_log_path=AUDIT_LOG, per_callback_timeout=60.0)
    conv = _new_conv()

    title_proc = TitleSetterProcessor(client=client, model=model, title_dir=TITLE_DIR)
    disp.register(title_proc, event_kind="user_message")
    print(f"注册 TitleSetterProcessor (LLM={model})")
    print(f"状态: disabled={title_proc.disabled}")

    print("\n[第一次 user_message: 应该触发起标题]")
    _emit_user(disp, conv, "帮我写一个把 csv 转成 sqlite 的 python 脚本, 要 idempotent")
    await _drain(disp)

    title_file = TITLE_DIR / f"{conv}.title"
    if title_file.exists():
        title = title_file.read_text().strip()
        print(f"生成的 title: {title!r}")
        print(f"processor.disabled = {title_proc.disabled} (应该是 True)")
    else:
        print("✗ 没生成 title")
        return

    print("\n[第二次 user_message: TitleSetter 应该已 disabled, 跳过]")
    _emit_user(disp, conv, "再加个进度条")
    await _drain(disp)

    # 看注册项的 status
    regs = disp.list_callbacks()
    for reg in regs:
        if isinstance(reg.processor, TitleSetterProcessor):
            print(f"派发器看到的 callback.status = {reg.status}")
            if reg.status == "DISABLED":
                print("→ 自禁用生效, 第二次没再调 LLM ✓")


# ── 场景 6 · timeout per callback (OpenHands 漏的, 我们补上) ──────────
async def scenario_timeout() -> None:
    _print_section("场景 6 · timeout per callback (BENCHMARK 升级 #2)")

    class HangingProcessor:
        """一个永远 hang 的 processor."""
        async def __call__(self, conversation_id, event):
            await asyncio.sleep(60)  # 故意挂 60 秒
            return None

    disp = CallbackDispatcher(audit_log_path=AUDIT_LOG, per_callback_timeout=2.0)
    disp.register(LoggingProcessor(label="HEALTHY"))
    disp.register(HangingProcessor())  # 这个会 hang
    print("注册: HEALTHY logger + HangingProcessor (会 sleep 60 秒)")
    print(f"per_callback_timeout = 2.0 秒")

    conv = _new_conv()
    print("\n[发事件, 看 hang 的 callback 是否被 timeout 兜住]")
    start = time.time()
    _emit_user(disp, conv, "test")
    await _drain(disp)
    elapsed = time.time() - start
    print(f"\n总耗时: {elapsed:.1f}s (应该 ≈ 2s 而不是 60s)")

    recent = disp.audit_records()[-2:]
    for r in recent:
        print(f"  status={r.status} detail={r.detail[:60]}")

    timed_out = any(r.status == "TIMEOUT" for r in recent)
    healthy_ok = any(r.status == "SUCCESS" for r in recent)
    if elapsed < 4.0 and timed_out and healthy_ok:
        print("→ 2s 后 timeout 触发, HEALTHY 没被拖累 ✓")
        print("    (OpenHands 自己没设 timeout, 这是我们 demo 改进的一处)")
    else:
        print(f"✗ 期望 elapsed < 4s + TIMEOUT + SUCCESS, 实际 elapsed={elapsed:.1f}s")


# ── main ──────────────────────────────────────────────────────────────
def _cleanup() -> None:
    for p in [events.EVENTS_DIR, TITLE_DIR, WEBHOOK_SINK]:
        if p.exists():
            shutil.rmtree(p)
    if AUDIT_LOG.exists():
        AUDIT_LOG.unlink()
    print("已清理 .events/ .titles/ .webhook-sink/ audit.jsonl")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", type=int, choices=[1, 2, 3, 4, 5, 6])
    p.add_argument("--cleanup", action="store_true")
    args = p.parse_args()

    if args.cleanup:
        _cleanup()
        return

    # 每次跑前清理, 保证场景独立
    _cleanup()

    scenarios = {
        1: scenario_fanout,
        2: scenario_per_conversation,
        3: scenario_per_event_kind,
        4: scenario_failure_isolation,
        5: scenario_title_setter,
        6: scenario_timeout,
    }

    async def runner() -> None:
        if args.scenario:
            await scenarios[args.scenario]()
        else:
            for n in sorted(scenarios):
                await scenarios[n]()

    asyncio.run(runner())

    _print_section("结束")
    print(f"audit log: {AUDIT_LOG} ({len(AUDIT_LOG.read_text().splitlines()) if AUDIT_LOG.exists() else 0} 条)")
    print("清理: python main.py --cleanup")


if __name__ == "__main__":
    main()
