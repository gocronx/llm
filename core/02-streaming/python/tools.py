"""tools.py —— 工具注册表，沿用 01 demo 的写法。
这里只放一个 `get_weather`，演示流式 + 工具调用的 delta 累积就够了。"""
from __future__ import annotations

import json
from typing import Callable

TOOLS: dict[str, tuple[Callable, dict]] = {}


def tool(schema: dict):
    def deco(fn: Callable) -> Callable:
        TOOLS[schema["name"]] = (fn, schema)
        return fn
    return deco


@tool({
    "name": "get_weather",
    "description": "获取指定城市的天气",
    "parameters": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
})
def get_weather(city: str) -> dict:
    db = {"北京": (15, "晴"), "上海": (20, "多云"), "深圳": (25, "小雨")}
    t, cond = db.get(city, (18, "数据不可用"))
    return {"city": city, "temperature": t, "condition": cond}


def schemas() -> list[dict]:
    return [{"type": "function", "function": s} for _, s in TOOLS.values()]


def call(name: str, args: dict) -> str:
    fn, _ = TOOLS.get(name, (None, None))
    if fn is None:
        return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
    try:
        return json.dumps(fn(**args), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
