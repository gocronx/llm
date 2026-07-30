"""replay.py —— 从事件流重建对话状态. 这是 event sourcing 的灵魂.

任何时候新进程启动, 不管对话之前跑过几轮, 只要事件文件还在,
replay 一次就回到当前状态. 这就是为什么 OpenHands 服务器可以随便重启.
"""

from __future__ import annotations

from events import load_all


def replay_to_messages(conversation_id: str) -> list[dict]:
    """把事件流重建成 OpenAI Chat Completions 格式的 messages 列表.

    只处理 user_message / assistant_message 两种事件; tool_call / tool_result
    类的事件需要更复杂的还原 (因为 OpenAI 格式里它们是 assistant 消息的子结构),
    demo 暂不涉及.

    返回的 messages 可以直接喂给 chat.completions.create.
    """
    messages: list[dict] = []
    for ev in load_all(conversation_id):
        if ev.kind == "user_message":
            messages.append({"role": "user", "content": ev.payload["text"]})
        elif ev.kind == "assistant_message":
            messages.append({"role": "assistant", "content": ev.payload["text"]})
        # 其它类型 (system_event, tool_call, ...) demo 阶段忽略
    return messages


def summarize(conversation_id: str) -> dict:
    """给个对话的人类可读概览. 主要给 --inspect 命令用."""
    events = load_all(conversation_id)
    by_kind: dict[str, int] = {}
    for ev in events:
        by_kind[ev.kind] = by_kind.get(ev.kind, 0) + 1
    return {
        "conversation_id": conversation_id,
        "total_events": len(events),
        "by_kind": by_kind,
        "first_event_at": events[0].timestamp if events else None,
        "last_event_at": events[-1].timestamp if events else None,
    }
