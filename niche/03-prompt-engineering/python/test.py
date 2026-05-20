"""test.py —— 用 mock client 测各技术构造的 messages 结构。"""
from __future__ import annotations

from unittest.mock import MagicMock

from techniques import chain_of_thought, few_shot, structured, system_prompt


def _mock_client(returns: str | dict = "ok"):
    """返回一个 mock OpenAI client，并把它收到的最后一次 messages 暴露在 .last_messages。"""
    client = MagicMock()

    def create(model, messages, **kw):
        client.last_messages = messages
        client.last_kw = kw
        resp = MagicMock()
        content = returns if isinstance(returns, str) else __import__("json").dumps(returns)
        resp.choices = [MagicMock(message=MagicMock(content=content))]
        return resp

    client.chat.completions.create.side_effect = create
    return client


def test_system_prompt_has_system_message() -> bool:
    c = _mock_client()
    system_prompt(c, "m", "q", role="roleX")
    msgs = c.last_messages
    ok = msgs[0]["role"] == "system" and msgs[0]["content"] == "roleX"
    print(f"{'✓' if ok else '✗'} system_prompt puts role in system message")
    return ok


def test_few_shot_alternates() -> bool:
    c = _mock_client()
    few_shot(c, "m", "real q", examples=[("u1", "a1"), ("u2", "a2")])
    msgs = c.last_messages
    roles = [m["role"] for m in msgs]
    ok = roles == ["user", "assistant", "user", "assistant", "user"] \
        and msgs[-1]["content"] == "real q"
    print(f"{'✓' if ok else '✗'} few_shot alternates user/assistant ({roles})")
    return ok


def test_cot_has_step_by_step_instruction() -> bool:
    c = _mock_client()
    chain_of_thought(c, "m", "23-5+12 = ?")
    sys_content = c.last_messages[0]["content"]
    ok = "推理" in sys_content or "step" in sys_content.lower()
    print(f"{'✓' if ok else '✗'} CoT system has step-by-step instruction")
    return ok


def test_structured_uses_json_schema() -> bool:
    c = _mock_client(returns={"x": 1})
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"], "additionalProperties": False}
    out = structured(c, "m", "give me x=1", schema)
    rf = c.last_kw.get("response_format", {})
    ok = rf.get("type") == "json_schema" and rf["json_schema"]["strict"] is True and out == {"x": 1}
    print(f"{'✓' if ok else '✗'} structured uses strict json_schema")
    return ok


def main() -> None:
    passed = sum([
        test_system_prompt_has_system_message(),
        test_few_shot_alternates(),
        test_cot_has_step_by_step_instruction(),
        test_structured_uses_json_schema(),
    ])
    print(f"\n{passed}/4 passed")


if __name__ == "__main__":
    main()
