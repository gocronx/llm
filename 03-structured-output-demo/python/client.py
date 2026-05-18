"""client.py —— 结构化输出的封装。整文件 cp 进项目即可。

`response_format={"type":"json_schema","json_schema":{...,"strict":true}}`
让 OpenAI 在 token 解码时做约束（grammar-constrained decoding），保证返回
就是合法 JSON 且严格符合 schema。比"prompt 里写一句请返回 JSON"靠谱得多。
"""
from __future__ import annotations

import json
from typing import Any

from openai import OpenAI


def extract(client: OpenAI, model: str, system: str, user: str, schema: dict,
            name: str = "result") -> dict[str, Any]:
    """约束 LLM 必须按 schema 返回 JSON，直接返回 parse 后的 dict。"""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": name, "schema": schema, "strict": True},
        },
    )
    # strict 模式下 content 就是合法 JSON 字符串；不需要 try/except，json.loads
    # 抛错说明模型/网关压根没遵守 strict，是要修的 bug 不是要 swallow 的异常
    return json.loads(resp.choices[0].message.content or "{}")
