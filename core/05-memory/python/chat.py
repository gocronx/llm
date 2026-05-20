"""chat.py —— 一个 Memory + LLM 客户端 = 一个会话。整文件 cp 进项目即可。"""
from __future__ import annotations

from openai import OpenAI

from memory import Memory


class Chat:
    def __init__(self, client: OpenAI, model: str, memory: Memory):
        self.client = client
        self.model = model
        self.memory = memory

    def ask(self, user_msg: str) -> str:
        self.memory.append("user", user_msg)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=self.memory.messages(),
            max_tokens=200,
            temperature=0.3,
        )
        answer = resp.choices[0].message.content or ""
        self.memory.append("assistant", answer)
        return answer


def make_summarizer(client: OpenAI, model: str):
    """工厂：返回一个把 messages 压成一段事实的 summarize_fn。"""
    def fn(msgs: list[dict]) -> str:
        joined = "\n".join(f"{m['role']}: {m['content']}" for m in msgs)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "提取对话中的关键事实，按 - 列表，每条一行。"},
                {"role": "user", "content": joined},
            ],
            max_tokens=150,
            temperature=0.0,
        )
        return resp.choices[0].message.content or ""
    return fn
