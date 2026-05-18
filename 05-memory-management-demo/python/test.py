"""test.py —— 不需要 LLM 的纯逻辑测试。
验证四种 memory 的裁剪行为符合预期。"""
from __future__ import annotations

from memory import Full, Summary, Tokens, Window


def test_full() -> bool:
    m = Full("sys")
    for i in range(5):
        m.append("user", f"q{i}")
        m.append("assistant", f"a{i}")
    ok = len(m.messages()) == 1 + 10  # system + 10 条
    print(f"{'✓' if ok else '✗'} full: kept {len(m.messages())-1} msgs")
    return ok


def test_window() -> bool:
    m = Window("sys", k=4)
    for i in range(5):
        m.append("user", f"q{i}")
        m.append("assistant", f"a{i}")
    # 10 条进，window=4，留最后 4 条
    contents = [x["content"] for x in m.messages()[1:]]
    ok = contents == ["q3", "a3", "q4", "a4"]
    print(f"{'✓' if ok else '✗'} window(4): {contents}")
    return ok


def test_tokens() -> bool:
    # 每条 ~7 token，max=20 应该只能留 2 条
    m = Tokens("s", max_tokens=20)
    for i in range(10):
        m.append("user", "中文中文中文中文")  # ~5t
    # 每条 ~5 token，system "s" 是英文 ~0 token，20 / 5 = 4 条上限
    kept = len(m.messages()) - 1
    ok = kept <= 4
    print(f"{'✓' if ok else '✗'} tokens(20): kept {kept} msgs (≤4)")
    return ok


def test_summary() -> bool:
    calls: list[list[dict]] = []
    def fake_summarize(msgs: list[dict]) -> str:
        calls.append(list(msgs))
        return "summary"

    m = Summary("sys", summarize_fn=fake_summarize, k=4)
    for i in range(8):
        m.append("user" if i % 2 == 0 else "assistant", f"x{i}")
    # 8 条总共触发摘要 2 次（在第 4 和第 8 条时）
    # 第 4 次时 _msgs 长度 == 4，触发，清空
    # 接着第 5~8 又攒 4 条，再触发，清空
    ok = len(calls) == 2 and m.summary.count("summary") == 2
    print(f"{'✓' if ok else '✗'} summary(k=4): triggered {len(calls)}x, summary={m.summary!r}")
    return ok


def main() -> None:
    passed = sum([test_full(), test_window(), test_tokens(), test_summary()])
    print(f"\n{passed}/4 passed")


if __name__ == "__main__":
    main()
