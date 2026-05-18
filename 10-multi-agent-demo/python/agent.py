"""agent.py —— 单 Agent：name + role(system prompt) + 一次 LLM 调用。
不带 function call（多 agent 协作的主要复杂度在 orchestration，单 agent 就保持纯文本）。
整文件 cp 进项目即可。"""
from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI


@dataclass
class Agent:
    name: str
    role: str       # 这个 agent 的 system prompt（角色 + 指令）
    client: OpenAI
    model: str
    temperature: float = 0.3

    def execute(self, task: str, context: str = "") -> str:
        """跑一次任务。context 是上游 agent 的输出汇总，作为 user message 的补充。"""
        user = task if not context else f"{task}\n\n上游产物：\n{context}"
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.role},
                {"role": "user", "content": user},
            ],
            temperature=self.temperature,
            max_tokens=400,
        )
        return resp.choices[0].message.content or ""
