"""tools.py —— 复用 09 的工具集 + 新增一个会返回大块文本的 web_fetch.

新增 web_fetch 是故意的: 它返回 8KB+ 文本, 跑几轮就让 microcompact + budget 都生效,
不加这个治理代码摸不到边."""
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
    "description": "获取指定城市天气",
    "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
})
def get_weather(city: str) -> dict:
    db = {"北京": (15, "晴"), "上海": (20, "多云"), "深圳": (25, "小雨"), "杭州": (18, "阴")}
    t, cond = db.get(city, (18, "数据不可用"))
    return {"city": city, "temperature": t, "condition": cond}


@tool({
    "name": "search_products",
    "description": "搜索产品 (大块只读数据, 可压缩)",
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
        {"id": i, "name": f"产品-{i}", "price": 100 * i,
         "desc": f"这是产品 {i} 的详细描述, " * 30}
        for i in range(1, 21)
    ]
    hits = [p for p in products if (not query or query in p["name"]) and min_price <= p["price"] <= max_price]
    return {"count": len(hits), "results": hits}


@tool({
    "name": "web_fetch",
    "description": "抓取网页文本 (返回可能很大, 数 KB)",
    "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
})
def web_fetch(url: str) -> dict:
    # 模拟一篇 8KB 左右的网页
    body = (f"# 关于 {url} 的内容\n\n" + "Lorem ipsum dolor sit amet, " * 200)
    return {"url": url, "title": f"{url} 文章", "body": body, "byte_size": len(body)}


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
