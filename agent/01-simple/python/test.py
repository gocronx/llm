"""test.py —— 用 mock LLM 测试 Agent 的 ReAct 循环逻辑，不调外网。"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from agent import Agent


def _mock_msg(tool_calls=None, content=None):
    msg = MagicMock()
    msg.tool_calls = tool_calls
    msg.content = content
    msg.model_dump = lambda exclude_none: {"role": "assistant", "tool_calls": tool_calls, "content": content}
    return msg


def _mock_response(message):
    resp = MagicMock()
    resp.choices = [MagicMock(message=message)]
    return resp


def test_immediate_answer() -> bool:
    """LLM 第一轮就给 content，不调工具 → 直接返回。"""
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_response(_mock_msg(content="hi"))
    a = Agent(client, "m")
    out = a.run("你好")
    ok = out == "hi" and len(a.steps) == 0
    print(f"{'✓' if ok else '✗'} immediate answer ({out!r})")
    return ok


def test_tool_then_answer() -> bool:
    """第一轮调 get_weather，第二轮给 content。"""
    tc = MagicMock()
    tc.id = "c1"
    tc.function.name = "get_weather"
    tc.function.arguments = '{"city":"北京"}'

    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _mock_response(_mock_msg(tool_calls=[tc])),
        _mock_response(_mock_msg(content="北京天气晴")),
    ]
    a = Agent(client, "m")
    out = a.run("北京天气")
    ok = out == "北京天气晴" and len(a.steps) == 1 and a.steps[0].tool == "get_weather"
    print(f"{'✓' if ok else '✗'} tool then answer (steps={[s.tool for s in a.steps]})")
    return ok


def test_max_iterations_guard() -> bool:
    """如果 LLM 一直返回 tool_call，到达 max_iterations 时退出。"""
    tc = MagicMock()
    tc.id = "c1"
    tc.function.name = "get_weather"
    tc.function.arguments = '{"city":"x"}'

    client = MagicMock()
    client.chat.completions.create.return_value = _mock_response(_mock_msg(tool_calls=[tc], content=""))
    a = Agent(client, "m", max_iterations=3)
    out = a.run("infinite")
    ok = len(a.steps) == 3 and "(达到最大迭代次数" in out
    print(f"{'✓' if ok else '✗'} max iterations guard (steps={len(a.steps)})")
    return ok


def main() -> None:
    passed = sum([test_immediate_answer(), test_tool_then_answer(), test_max_iterations_guard()])
    print(f"\n{passed}/3 passed")


if __name__ == "__main__":
    main()
