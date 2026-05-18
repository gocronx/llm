"""client.py —— 流式输出的两种姿势。整文件 cp 进项目即可。

`stream_text()` —— 纯文本流式：iterator yield 每一段 delta content。
`stream_with_tools()` —— 流式 + function call：需要把分块到达的 tool_calls 累
积成完整决策，再执行工具，再发起第二轮（仍然是流式）输出最终回答。

关键点：OpenAI SDK 已经把 SSE 分帧/`data: [DONE]` 这些 HTTP 协议细节藏掉了，
我们只关心"chunk 流"本身。不要再手撸 requests + iter_lines。
"""
from __future__ import annotations

import json
from typing import Iterator

from openai import OpenAI

from tools import call, schemas


def stream_text(client: OpenAI, model: str, user_msg: str) -> Iterator[str]:
    """纯文本流式：逐段 yield content。"""
    chunks = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_msg}],
        stream=True,
    )
    for chunk in chunks:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


def stream_with_tools(client: OpenAI, model: str, user_msg: str) -> Iterator[dict]:
    """流式 + function call。yield 事件字典，调用方自己决定怎么渲染：
        {"type": "tool_call", "name": str, "args": dict, "result": str}
        {"type": "text", "delta": str}
    """
    messages: list[dict] = [{"role": "user", "content": user_msg}]

    # 第一轮：流式收 tool_calls。模型可能在 stream 中边吐文本边吐工具调用，
    # 文本部分这里不渲染（多数模型在决定调工具时根本不吐文本）。
    first_chunks = client.chat.completions.create(
        model=model, messages=messages, tools=schemas(), stream=True,
    )

    # accumulator: index -> {"id", "name", "args"}。
    # OpenAI 流式协议里 tool_calls 是按 index 分槽位下发，name/arguments 都
    # 可能分多次到达；arguments 永远是 JSON 字符串，必须用字符串拼接而不是
    # dict.update —— 半截 JSON 不是合法字典。
    acc: dict[int, dict] = {}
    for chunk in first_chunks:
        for tc in (chunk.choices[0].delta.tool_calls or []):
            slot = acc.setdefault(tc.index, {"id": "", "name": "", "args": ""})
            if tc.id:
                slot["id"] = tc.id
            if tc.function and tc.function.name:
                slot["name"] = tc.function.name
            if tc.function and tc.function.arguments:
                slot["args"] += tc.function.arguments

    if not acc:
        # 没要调工具：直接重发一次非流式不划算，重跑一次普通 stream
        yield from ({"type": "text", "delta": d} for d in stream_text(client, model, user_msg))
        return

    # 把 assistant 的 tool_calls 决策回灌（用 OpenAI 期望的扁平结构）
    tool_calls_payload = [
        {"id": s["id"], "type": "function",
         "function": {"name": s["name"], "arguments": s["args"]}}
        for s in acc.values()
    ]
    messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls_payload})

    # 执行每个工具，作为 role=tool 消息回灌
    for slot in acc.values():
        result = call(slot["name"], json.loads(slot["args"]))
        yield {"type": "tool_call", "name": slot["name"],
               "args": json.loads(slot["args"]), "result": result}
        messages.append({"role": "tool", "tool_call_id": slot["id"], "content": result})

    # 第二轮：流式吐最终回答
    second = client.chat.completions.create(model=model, messages=messages, stream=True)
    for chunk in second:
        delta = chunk.choices[0].delta
        if delta.content:
            yield {"type": "text", "delta": delta.content}
