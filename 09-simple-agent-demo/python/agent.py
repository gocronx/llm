"""agent.py —— 最小 ReAct 风格 Agent。整文件 cp 进项目即可。

Agent 不是魔法，就是把 01 demo 的"一次 function call 往返"包成多轮循环：
  while LLM 还在调工具 and 没超 max_iterations:
      调工具 -> 把结果回灌 -> 再问 LLM

终止条件：LLM 给出 content（不带 tool_calls）即视为最终答案。
失败兜底：到 max_iterations 仍未给答案，返回最后一次内容（不抛异常，方便上游）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from openai import OpenAI

from tools import call, schemas


SYSTEM = """你是一个会用工具的助手。
- 需要外部信息时调用工具，工具返回后再决定下一步
- 信息足够就直接回答，不要为了用工具而用工具
- 一次任务最多调 8 次工具，多步任务请规划好步骤"""


@dataclass
class Step:
    """记录一次工具调用，便于调试/追溯。"""
    tool: str
    args: dict
    result: str


@dataclass
class Agent:
    client: OpenAI
    model: str
    max_iterations: int = 8
    on_step: Callable[[Step], None] | None = None
    steps: list[Step] = field(default_factory=list)

    def run(self, task: str) -> str:
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": task},
        ]
        last_content = ""
        for _ in range(self.max_iterations):
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages, tools=schemas(),
                temperature=0.3, max_tokens=600,
            )
            msg = resp.choices[0].message
            last_content = msg.content or ""

            if not msg.tool_calls:
                # 终止：LLM 给出最终文本回答
                return last_content

            messages.append(msg.model_dump(exclude_none=True))
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                result = call(tc.function.name, args)
                step = Step(tc.function.name, args, result)
                self.steps.append(step)
                if self.on_step:
                    self.on_step(step)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        return last_content or "(达到最大迭代次数仍未给出答案)"
