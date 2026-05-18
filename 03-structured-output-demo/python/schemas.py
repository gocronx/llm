"""schemas.py —— 三个示例 JSON Schema。
注意 OpenAI strict 模式的硬性要求：
  1) 每个 object 都要写 `additionalProperties: false`
  2) `required` 必须列出 properties 里的所有 key
  3) 不支持 `default` / `format` / 部分 `pattern`
这些规则违反时 OpenAI 直接报 400，不会"宽松降级"。"""
from __future__ import annotations

# 1) 简历提取：嵌套对象 + 数组。
RESUME = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "position": {"type": "string"},
        "email": {"type": "string"},
        "skills": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["name", "age", "position", "email", "skills"],
    "additionalProperties": False,
}

# 2) 产品信息：嵌套对象 + enum。
PRODUCT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "brand": {"type": "string"},
        "price": {
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "currency": {"type": "string", "enum": ["CNY", "USD", "EUR"]},
            },
            "required": ["amount", "currency"],
            "additionalProperties": False,
        },
        "in_stock": {"type": "boolean"},
    },
    "required": ["name", "brand", "price", "in_stock"],
    "additionalProperties": False,
}

# 3) 情感分类：enum 限定输出域。
SENTIMENT = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "enum": ["positive", "neutral", "negative"]},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["label", "confidence", "reason"],
    "additionalProperties": False,
}
