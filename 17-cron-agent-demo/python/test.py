"""test.py —— state 模块 + 不依赖 LLM 的 job 逻辑测试。"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import state


def t(label: str, cond: bool) -> bool:
    print(f"{'✓' if cond else '✗'} {label}")
    return cond


def setup() -> None:
    # 把 state 文件指向临时位置
    import tempfile
    tmpdir = Path(tempfile.mkdtemp())
    state.STATE_FILE = tmpdir / "state.json"


def main() -> None:
    setup()
    passed = 0

    # state.set_ / get
    state.set_("foo", 42)
    passed += t("state.set_/get roundtrip", state.get("foo") == 42)

    # 默认值
    passed += t("state.get default", state.get("missing", "x") == "x")

    # append_event 写入并保留最近 N 条
    for i in range(5):
        state.append_event({"job": "h", "i": i})
    events = state.get_events_since(seconds_ago=10_000)
    passed += t("append_event 5 events", len(events) == 5 and events[-1]["i"] == 4)

    # ts 字段被自动加上
    passed += t("append_event auto ts", all("ts" in e for e in events))

    # get_events_since 过滤掉过老的事件
    # 模拟"在很久以前写的事件" —— 直接污染 state file
    data = {"events": [
        {"ts": "2000-01-01T00:00:00", "job": "old"},
        *events,
    ]}
    state.STATE_FILE.write_text(__import__("json").dumps(data), encoding="utf-8")
    recent = state.get_events_since(seconds_ago=10)
    passed += t("get_events_since filters old", not any(e.get("job") == "old" for e in recent))

    # MAX_EVENTS 上限
    state.STATE_FILE.write_text("{}", encoding="utf-8")
    for i in range(state.MAX_EVENTS + 50):
        state.append_event({"job": "spam", "i": i})
    final_count = len(state.get_events_since(10_000))
    passed += t(f"MAX_EVENTS cap = {state.MAX_EVENTS}", final_count == state.MAX_EVENTS)

    print(f"\n{passed}/6 passed")


if __name__ == "__main__":
    main()
