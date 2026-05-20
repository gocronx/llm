"""techniques.py —— 四种 prompt engineering 技术。整文件 cp 进项目即可。

每种技术都是一个 ask(client, model, user_input) -> str：
  baseline       —— 啥都不加，直接问
  system_prompt  —— 角色定义在 system message 里
  few_shot       —— user/assistant 两到三对示例放在前面，结尾接真问题
  chain_of_thought —— "一步步思考后再给最终答案"
  structured     —— response_format=json_schema 强制结构化

可组合：技术不是互斥的，生产里 system_prompt + few_shot + structured 经常一起用。
"""
from __future__ import annotations

import json

from openai import OpenAI


def baseline(client: OpenAI, model: str, user_input: str) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_input}],
        temperature=0,
    )
    return resp.choices[0].message.content or ""


def system_prompt(client: OpenAI, model: str, user_input: str,
                  role: str = "你是一个简短的助手，每次只用一句话回答。") -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": role},
            {"role": "user", "content": user_input},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content or ""


def few_shot(client: OpenAI, model: str, user_input: str,
             examples: list[tuple[str, str]] | None = None) -> str:
    """examples = [(user_msg, assistant_msg), ...]。
    每对放成两条 message，最后接真问题。模型从示例学输出格式比 prompt 里写"请按以下格式"靠谱。"""
    examples = examples or [
        ("把这句翻译成英文：今天天气真好", "What nice weather today."),
        ("把这句翻译成英文：我饿了", "I'm hungry."),
    ]
    msgs = []
    for u, a in examples:
        msgs.append({"role": "user", "content": u})
        msgs.append({"role": "assistant", "content": a})
    msgs.append({"role": "user", "content": user_input})
    resp = client.chat.completions.create(model=model, messages=msgs, temperature=0)
    return resp.choices[0].message.content or ""


def chain_of_thought(client: OpenAI, model: str, user_input: str) -> str:
    """让模型先 "Let's think step by step" 再给答案。数学/推理题准确率显著提升。
    代价是 token 多 2-5 倍。"""
    sys = "回答前先用一步步推理（标题写 '思考：'），最后用 '答案：' 给最终结论。"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user_input},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content or ""


def structured(client: OpenAI, model: str, user_input: str, schema: dict, name: str = "out") -> dict:
    """强制 JSON 输出。这是最稳的"控制输出"方式，比 prompt 里写"请返回 JSON"准 100%。"""
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_input}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": name, "schema": schema, "strict": True},
        },
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content or "{}")
