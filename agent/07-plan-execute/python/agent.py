"""agent.py —— Plan-and-Execute Agent。

跟 01-simple 的 ReAct 是两种思路：
  ReAct          每轮临时想"下一步干啥"，看一步走一步。
  Plan-Execute   先让 LLM 把整件事拆成一份计划，再一条条做掉。

同一个 LLM 扮三个角色，靠 system prompt 区分：
  planner      把 goal 拆成步骤清单（planner.py）
  executor     拿工具把单个步骤做掉，内部一个短 ReAct 小循环
  synthesizer  把所有步骤结果汇成给用户的最终答案

replan 是这个范式跟"念一遍待办清单"的区别：做完一步回头看，结果跟预期对不上
就改掉剩余步骤。关掉 replan（replan=False）就退化成静态计划，适合对比着看。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from openai import OpenAI
from planner import make_plan, revise_plan
from tools import call, schemas

EXECUTOR_SYS = """你是执行器，只负责完成交给你的这一步，别管别的步骤。
需要外部信息就调工具，工具返回后把这一步的结论用一句话讲清楚。"""

SYNTH_SYS = """你是汇总器。根据各步骤的结果，用中文给用户一个完整直接的最终答案。
别罗列步骤、别说"根据以上"，直接给结论。"""


@dataclass
class Done:
    """一条已执行步骤的记录。"""

    step: str
    result: str


@dataclass
class PlanExecuteAgent:
    client: OpenAI
    model: str
    max_steps: int = 6
    max_tool_calls_per_step: int = 3
    replan: bool = True
    on_event: Callable[[str, str], None] | None = None
    plan: list[str] = field(default_factory=list)
    transcript: list[Done] = field(default_factory=list)

    def run(self, goal: str) -> str:
        self.plan = make_plan(self.client, self.model, goal)
        self._emit("plan", " | ".join(self.plan) or "(空计划)")

        for _ in range(self.max_steps):
            if not self.plan:
                break
            step = self.plan.pop(0)
            result = self._execute(goal, step)
            self.transcript.append(Done(step, result))
            self._emit("step", f"{step} -> {result[:80]}")
            if self.replan and self.plan:
                self.plan = self._replan(goal)
                self._emit("replan", " | ".join(self.plan) or "(已无剩余)")

        return self._synthesize(goal)

    def _execute(self, goal: str, step: str) -> str:
        """单步执行：一个上限很低的 ReAct 小循环，跑完就交回结果。"""
        messages: list[dict] = [
            {"role": "system", "content": EXECUTOR_SYS},
            {"role": "user", "content": f"总目标：{goal}\n现在只做这一步：{step}"},
        ]
        last = ""
        for _ in range(self.max_tool_calls_per_step + 1):
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=schemas(),
                temperature=0.2,
                max_tokens=500,
            )
            msg = resp.choices[0].message
            last = msg.content or last
            if not msg.tool_calls:
                return last
            messages.append(msg.model_dump(exclude_none=True))
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                out = call(tc.function.name, args)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})
        return last or "(本步未产出文本结果)"

    def _replan(self, goal: str) -> list[str]:
        done = "\n".join(f"- {d.step} → {d.result[:120]}" for d in self.transcript)
        return revise_plan(self.client, self.model, goal, done, self.plan)

    def _synthesize(self, goal: str) -> str:
        if not self.transcript:
            return "(没有可用结果)"
        body = "\n".join(f"步骤：{d.step}\n结果：{d.result}" for d in self.transcript)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYNTH_SYS},
                {"role": "user", "content": f"目标：{goal}\n\n{body}"},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        return resp.choices[0].message.content or ""

    def _emit(self, kind: str, detail: str) -> None:
        if self.on_event:
            self.on_event(kind, detail)
