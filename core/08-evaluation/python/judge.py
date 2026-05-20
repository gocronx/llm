"""judge.py —— LLM-as-Judge：当 metric 是 `llm_judge` 时，用另一个 LLM 调用打分。
整文件 cp 进项目即可。

三种姿势：
  - binary（pass/fail + 理由）
  - score（1~5 分 + 理由）
  - pairwise（A vs B 哪个更好，避免单 LLM 给分漂移）

只暴露第一种 + JSON 结构化输出，因为这是 dataset 评测里最常用的。pairwise
留给 main.py 演示。
"""
from __future__ import annotations

import json

from openai import OpenAI

_SCHEMA = {
    "type": "object",
    "properties": {
        "pass": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["pass", "reason"],
    "additionalProperties": False,
}


def binary(client: OpenAI, model: str, question: str, rubric: str, answer: str) -> tuple[bool, str]:
    """裁判：按 rubric 判断 answer 对不对。强制结构化输出。"""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是严格但公平的评分员。按 rubric 判定，不要被措辞华丽影响。"},
            {"role": "user", "content": (
                f"问题：{question}\n\n"
                f"评分标准：{rubric}\n\n"
                f"被评答案：{answer}\n\n"
                "请判断答案是否满足评分标准。"
            )},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "judgment", "schema": _SCHEMA, "strict": True},
        },
        temperature=0,
    )
    out = json.loads(resp.choices[0].message.content or "{}")
    return bool(out.get("pass")), str(out.get("reason", ""))


def pairwise(client: OpenAI, model: str, question: str, a: str, b: str) -> str:
    """裁判：A 和 B 谁更好。返回 "A" / "B" / "tie"。
    给两个候选答案对比 —— 比单 LLM 直接打分稳得多，避免分数漂移。"""
    schema = {
        "type": "object",
        "properties": {"winner": {"type": "string", "enum": ["A", "B", "tie"]}, "reason": {"type": "string"}},
        "required": ["winner", "reason"],
        "additionalProperties": False,
    }
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是中立评审员。只比较两个答案的相对质量，不要被位置 A/B 影响。"},
            {"role": "user", "content": f"问题：{question}\n\nA：{a}\n\nB：{b}\n\n哪个更好？"},
        ],
        response_format={"type": "json_schema", "json_schema": {"name": "verdict", "schema": schema, "strict": True}},
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content or "{}").get("winner", "tie")
