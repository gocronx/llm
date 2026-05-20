"""tools.py —— 工具注册表，沿用 01 demo 的写法。
Agent 拿到的工具集应该是有限且语义明确的；这里给 3 个就够演示 ReAct 多步推理。"""
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
    db = {"北京": (15, "晴"), "上海": (20, "多云"), "深圳": (25, "小雨"), "杭州": (18, "阴")}
    t, cond = db.get(city, (18, "数据不可用"))
    return {"city": city, "temperature": t, "condition": cond}


@tool({
    "name": "calculate",
    "description": "执行四则运算",
    "parameters": {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["add", "sub", "mul", "div"]},
            "a": {"type": "number"},
            "b": {"type": "number"},
        },
        "required": ["op", "a", "b"],
    },
})
def calculate(op: str, a: float, b: float) -> dict:
    if op == "div" and b == 0:
        return {"error": "division by zero"}
    return {"result": {"add": a + b, "sub": a - b, "mul": a * b, "div": a / b if b else None}[op]}


@tool({
    "name": "search_products",
    "description": "搜索产品。可按关键词和价格区间过滤。",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "min_price": {"type": "number"},
            "max_price": {"type": "number"},
        },
    },
})
def search_products(query: str = "", min_price: float = 0, max_price: float = float("inf")) -> dict:
    products = [
        {"id": 1, "name": "笔记本电脑", "price": 5999},
        {"id": 2, "name": "机械键盘", "price": 599},
        {"id": 3, "name": "无线鼠标", "price": 199},
        {"id": 4, "name": "手机 A", "price": 3999},
        {"id": 5, "name": "手机 B", "price": 5999},
    ]
    hits = [p for p in products if (not query or query in p["name"]) and min_price <= p["price"] <= max_price]
    return {"count": len(hits), "results": hits}


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
