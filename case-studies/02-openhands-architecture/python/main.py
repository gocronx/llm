"""main.py —— event-sourced 对话 CLI. 跑两次就能看见"重启复活".

用法:
    python main.py <conv_id> "你的消息"   # 发一条消息
    python main.py <conv_id> --inspect     # 看事件流
    python main.py <conv_id> --clear       # 清空这个对话
    python main.py --list                  # 列出所有对话
    python main.py --clear-all             # 清空全部对话

核心演示流程 (运行 4 次):
    1. python main.py session-a "记住我用 ramen 当用户名占位符"
       → 事件磁盘: 2 条 (user + assistant)
    2. python main.py session-a "给我写个 flask hello world, 用我的占位符"
       → 事件磁盘: 4 条
    3. python main.py session-a --inspect
       → 看完整事件流; 注意每条都是独立 JSON 文件
    4. python main.py session-a "再写一个 fastapi 版本, 用同样的占位符"
       → 事件磁盘: 6 条, 模型自动遵守占位符 (从 replay 出的 messages 中获知)

每次运行都是新 Python 进程. 对话状态完全来自磁盘 replay.
对应 ANALYSIS.md 的"图 2 · 重启复活".
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

import events
import httpx
from dotenv import load_dotenv
from openai import OpenAI
from replay import replay_to_messages, summarize

load_dotenv()


def _make_client() -> tuple[OpenAI, str]:
    """构造 OpenAI 客户端. 跟项目其它 demo 共享配置约定 (.env)."""
    http = httpx.Client(trust_env=False, timeout=60.0)
    client = OpenAI(
        base_url=os.environ["API_BASE_URL"],
        api_key=os.environ.get("API_KEY", "not-needed"),
        http_client=http,
    )
    model = os.environ["MODEL_ID"]
    return client, model


def send_message(conv_id: str, user_text: str) -> None:
    """跑一轮对话. 这是 demo 的核心: 5 步 = OpenHands 单轮的最小骨架."""
    # 1. 持久化用户事件 (App Server 层做的事)
    user_ev = events.Event(
        kind="user_message",
        conversation_id=conv_id,
        payload={"text": user_text},
    )
    events.append(user_ev)

    # 2. 从事件流 replay 出当前对话状态 (Agent Server 层做的事)
    history = replay_to_messages(conv_id)
    messages = [{"role": "system", "content": "你是简洁有用的助手. 中文回答, 别说教."}] + history

    print(f"[历史: {len(history)} 条消息从事件流 replay 出来]")

    # 3. 调 LLM
    client, model = _make_client()
    resp = client.chat.completions.create(model=model, messages=messages, temperature=0.7)
    reply = resp.choices[0].message.content or ""

    # 4. 持久化 assistant 事件
    asst_ev = events.Event(
        kind="assistant_message",
        conversation_id=conv_id,
        payload={"text": reply},
    )
    events.append(asst_ev)

    # 5. 输出 (生产里这步是 WebSocket 推给前端)
    print(f"\n[user] {user_text}")
    print(f"\n[assistant] {reply}")

    # 给个统计
    total = len(events.load_all(conv_id))
    print(f"\n[event store: {total} 条事件落盘]")


def inspect(conv_id: str) -> None:
    """打印事件流明细. 用来"看见"事件溯源."""
    info = summarize(conv_id)
    print(f"== 对话 {conv_id} ==")
    print(f"总事件数: {info['total_events']}")
    print(f"按类型: {info['by_kind']}")
    if info["first_event_at"]:
        print(f"首事件: {datetime.fromtimestamp(info['first_event_at']).isoformat(timespec='seconds')}")
        print(f"末事件: {datetime.fromtimestamp(info['last_event_at']).isoformat(timespec='seconds')}")
    print()
    print("== 事件流 ==")
    for i, ev in enumerate(events.load_all(conv_id), 1):
        ts = datetime.fromtimestamp(ev.timestamp).strftime("%H:%M:%S")
        text = ev.payload.get("text", "")
        preview = text[:80].replace("\n", " ") + ("..." if len(text) > 80 else "")
        print(f"  [{i:3d}] {ts}  {ev.kind:20s}  {preview}")


def list_conversations() -> None:
    """列出磁盘上所有对话."""
    convs = events.list_conversations()
    if not convs:
        print("(no conversations yet)")
        return
    print(f"共 {len(convs)} 个对话:")
    for cid in convs:
        info = summarize(cid)
        print(f"  - {cid}  ({info['total_events']} 条事件)")


def main() -> None:
    p = argparse.ArgumentParser(description="Event-sourced 对话 demo")
    p.add_argument("conv_id", nargs="?", help="对话 ID")
    p.add_argument("text", nargs="?", help="要发送的消息")
    p.add_argument("--inspect", action="store_true", help="只看事件流, 不发消息")
    p.add_argument("--clear", action="store_true", help="清空此对话的事件")
    p.add_argument("--list", action="store_true", help="列出全部对话")
    p.add_argument("--clear-all", action="store_true", help="清空全部事件 (危险)")
    args = p.parse_args()

    if args.list:
        list_conversations()
        return
    if args.clear_all:
        events.clear()
        print("已清空 .events/ 全部内容")
        return
    if not args.conv_id:
        p.error("需要 conv_id (或用 --list / --clear-all)")

    if args.clear:
        events.clear(args.conv_id)
        print(f"已清空对话 {args.conv_id}")
        return
    if args.inspect:
        inspect(args.conv_id)
        return
    if not args.text:
        p.error("发消息需要 text 参数 (或用 --inspect 看事件流)")

    send_message(args.conv_id, args.text)


if __name__ == "__main__":
    main()
