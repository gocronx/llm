"""client.py —— Function Call 的两轮交互。整文件 cp 进项目即可。

第一轮：把 user message + tools 发给 LLM，LLM 返回 tool_calls 决策。
应用层：照决策执行工具，把结果作为 role=tool 消息回灌。
第二轮：LLM 看着工具结果生成最终自然语言回答。
"""
from __future__ import annotations

import json

from openai import OpenAI

from tools import call, schemas


def run(client: OpenAI, model: str, user_msg: str) -> str:
    """一次 function-call 往返。返回 LLM 的最终回答。"""
    messages: list[dict] = [{"role": "user", "content": user_msg}]

    first = client.chat.completions.create(model=model, messages=messages, tools=schemas())
    msg = first.choices[0].message

    if not msg.tool_calls:
        return msg.content or ""

    # assistant 的 tool_calls 决策必须回灌，否则下一轮 LLM 看不到自己刚才说了啥
    messages.append(msg.model_dump(exclude_none=True))

    # LLM 一次可能要调多个工具，全跑完再回 LLM
    for tc in msg.tool_calls:
        result = call(tc.function.name, json.loads(tc.function.arguments))
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    second = client.chat.completions.create(model=model, messages=messages)
    return second.choices[0].message.content or ""
