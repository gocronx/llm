"""util.py —— 共享小工具。"""
from __future__ import annotations

import json


def extract_json_array(text: str) -> list:
    """从模型回复里找最后一段合法 [...]。模型经常给一坨解释 + 数组，这种容错抽取最稳。"""
    for end in range(len(text) - 1, -1, -1):
        if text[end] != "]":
            continue
        depth = 0
        for start in range(end, -1, -1):
            if text[start] == "]":
                depth += 1
            elif text[start] == "[":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start: end + 1])
                    except json.JSONDecodeError:
                        break
    return []
