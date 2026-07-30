"""agent.py —— 09 的 Agent + 每轮治理. 整文件 cp 进项目即可.

跟 09 唯一区别: 每轮 LLM 调用前先 govern(messages), 拿治理后的版本去喂模型,
**但 self.messages 保持原状** —— 治理是"喂模型的视角", 不是"我的记忆"."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from governance import estimate_total_tokens, govern
from openai import OpenAI
from tools import call, schemas

SYSTEM = """你是会用工具的助手. 工具结果可能很长, 你要善用它们但别复述."""


@dataclass
class Step:
    tool: str
    args: dict
    result: str


@dataclass
class Agent:
    client: OpenAI
    model: str
    max_iterations: int = 20
    context_window_tokens: int = 8000   # 故意调小, 让治理生效
    max_tool_result_chars: int = 4000   # 故意调小
    on_step: Callable[[Step], None] | None = None
    on_govern: Callable[[int, int, int, int], None] | None = None  # (before_n, after_n, before_tok, after_tok)
    steps: list[Step] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)

    def run(self, task: str) -> str:
        if not self.messages:
            self.messages.append({"role": "system", "content": SYSTEM})
        self.messages.append({"role": "user", "content": task})

        last_content = ""
        for _ in range(self.max_iterations):
            # 治理是"喂模型的视角", 不动 self.messages 真实记忆
            view = govern(
                self.messages,
                context_window_tokens=self.context_window_tokens,
                max_tool_result_chars=self.max_tool_result_chars,
            )
            if self.on_govern:
                self.on_govern(
                    len(self.messages), len(view),
                    estimate_total_tokens(self.messages), estimate_total_tokens(view),
                )

            resp = self.client.chat.completions.create(
                model=self.model, messages=view, tools=schemas(),
                temperature=0.3, max_tokens=600,
            )
            msg = resp.choices[0].message
            last_content = msg.content or ""

            if not msg.tool_calls:
                return last_content

            self.messages.append(msg.model_dump(exclude_none=True))
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                result = call(tc.function.name, args)
                step = Step(tc.function.name, args, result)
                self.steps.append(step)
                if self.on_step:
                    self.on_step(step)
                self.messages.append({
                    "role": "tool", "tool_call_id": tc.id,
                    "name": tc.function.name, "content": result,
                })

        return last_content or "(达到最大迭代次数仍未给出答案)"
