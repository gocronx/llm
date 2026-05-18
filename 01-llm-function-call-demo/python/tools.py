"""tools.py —— 工具注册表：函数本体和它的 JSON Schema 配在一起。
新增工具只在这里加一项；client / main / test 都不用改。"""
from __future__ import annotations

import json
from typing import Callable

# name -> (callable, schema)。schema 即 OpenAI function 字段内容。
TOOLS: dict[str, tuple[Callable, dict]] = {}


def tool(schema: dict):
    """装饰器：注册一个 LLM 可调用的工具。"""
    def deco(fn: Callable) -> Callable:
        TOOLS[schema["name"]] = (fn, schema)
        return fn
    return deco


@tool({
    "name": "get_weather",
    "description": "获取指定城市的天气",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名，如：北京"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"},
        },
        "required": ["city"],
    },
})
def get_weather(city: str, unit: str = "celsius") -> dict:
    db = {"北京": (25, "晴"), "上海": (28, "多云"), "深圳": (30, "小雨")}
    c, cond = db.get(city, (20, "数据不可用"))
    temp = c if unit == "celsius" else round(c * 9 / 5 + 32, 1)
    return {"city": city, "temperature": temp, "unit": unit, "condition": cond}


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


# 让 LLM 自己拆"价格 500 以上" -> min_price=500，不要在 Python 里重新做 NLP。
@tool({
    "name": "search_products",
    "description": "搜索产品。可按关键词和价格区间过滤。",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "关键词，留空匹配全部"},
            "min_price": {"type": "number"},
            "max_price": {"type": "number"},
        },
    },
})
def search_products(
    query: str = "",
    min_price: float = 0,
    max_price: float = float("inf"),
) -> dict:
    products = [
        {"id": 1, "name": "笔记本电脑", "price": 5999},
        {"id": 2, "name": "机械键盘", "price": 599},
        {"id": 3, "name": "无线鼠标", "price": 199},
    ]
    hits = [p for p in products if (not query or query in p["name"]) and min_price <= p["price"] <= max_price]
    return {"count": len(hits), "results": hits}


def schemas() -> list[dict]:
    """返回给 LLM 的 tools 字段。"""
    return [{"type": "function", "function": s} for _, s in TOOLS.values()]


def call(name: str, args: dict) -> str:
    """执行一次工具调用，返回 JSON 字符串（OpenAI tool message 要的格式）。"""
    fn, _ = TOOLS.get(name, (None, None))
    if fn is None:
        return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
    try:
        return json.dumps(fn(**args), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
