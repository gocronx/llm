"""test.py —— 用 mock LLM 测 Plan-Execute 的规划/执行/改计划逻辑，不调外网。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from agent import PlanExecuteAgent
from planner import _parse


def _resp(content: str):
    msg = MagicMock()
    msg.tool_calls = None
    msg.content = content
    msg.model_dump = lambda exclude_none: {"role": "assistant", "content": content}
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class FakeLLM:
    """按 system prompt 判断当前角色，返回对应内容。executor 永远直接给文本（不调工具）。"""

    def __init__(self, plan, replan=None, exec_text="这一步做完了", final="最终答案"):
        self.plan = plan
        self.replan = replan
        self.exec_text = exec_text
        self.final = final
        self.roles: list[str] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, **kw):
        sys = messages[0]["content"]
        if sys.startswith("你是规划器") and "修订" not in sys:
            self.roles.append("plan")
            return _resp(json.dumps(self.plan, ensure_ascii=False))
        if "修订" in sys:
            self.roles.append("replan")
            steps = self.replan if self.replan is not None else self.plan
            return _resp(json.dumps(steps, ensure_ascii=False))
        if sys.startswith("你是汇总器"):
            self.roles.append("synth")
            return _resp(self.final)
        self.roles.append("exec")
        return _resp(self.exec_text)


def test_parse_json() -> bool:
    out = _parse('随便说点 ["查天气", "对比"] 后面也有字')
    ok = out == ["查天气", "对比"]
    print(f"{'✓' if ok else '✗'} parse json array ({out})")
    return ok


def test_parse_lines_fallback() -> bool:
    out = _parse("1. 查天气\n2. 对比\n- 给建议")
    ok = out == ["查天气", "对比", "给建议"]
    print(f"{'✓' if ok else '✗'} parse line fallback ({out})")
    return ok


def test_parse_garbage_returns_none() -> bool:
    ok = _parse("   ") is None
    print(f"{'✓' if ok else '✗'} garbage -> None")
    return ok


def test_plan_then_execute() -> bool:
    """静态计划（关 replan）：两步执行 + 一次汇总。"""
    llm = FakeLLM(plan=["查北京", "查上海"], final="北京更适合")
    a = PlanExecuteAgent(llm, "m", replan=False)
    out = a.run("对比北京上海")
    ok = (
        out == "北京更适合"
        and len(a.transcript) == 2
        and llm.roles == ["plan", "exec", "exec", "synth"]
    )
    print(
        f"{'✓' if ok else '✗'} plan then execute (steps={len(a.transcript)}, roles={llm.roles})"
    )
    return ok


def test_replan_can_shrink() -> bool:
    """改计划把剩余步骤清空 → 跑完第一步就停。"""
    llm = FakeLLM(plan=["a", "b", "c"], replan=[], final="done")
    a = PlanExecuteAgent(llm, "m", replan=True)
    a.run("x")
    ok = len(a.transcript) == 1 and a.plan == []
    print(f"{'✓' if ok else '✗'} replan shrinks plan (steps={len(a.transcript)})")
    return ok


def test_max_steps_guard() -> bool:
    """计划比 max_steps 长时，执行到上限就停，剩余步骤留在 plan 里。"""
    llm = FakeLLM(plan=["a", "b", "c", "d"])
    a = PlanExecuteAgent(llm, "m", max_steps=2, replan=False)
    a.run("x")
    ok = len(a.transcript) == 2 and a.plan == ["c", "d"]
    print(
        f"{'✓' if ok else '✗'} max steps guard (done={len(a.transcript)}, left={a.plan})"
    )
    return ok


def main() -> None:
    results = [
        test_parse_json(),
        test_parse_lines_fallback(),
        test_parse_garbage_returns_none(),
        test_plan_then_execute(),
        test_replan_can_shrink(),
        test_max_steps_guard(),
    ]
    print(f"\n{sum(results)}/{len(results)} passed")


if __name__ == "__main__":
    main()
