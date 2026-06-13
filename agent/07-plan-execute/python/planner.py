"""planner.py —— 规划与改计划。

把目标拆成有序步骤，以及执行到一半根据真实结果改剩余步骤。
输出要求是 JSON 字符串数组，但本地模型不保证守规矩，所以解析得宽松：
先按 JSON 读，读不到就按行切、去掉编号前缀。彻底读不出来返回 None，
让调用方决定是当成"没步骤"还是"沿用旧计划"。
"""

from __future__ import annotations

import json
import re

from openai import OpenAI

PLAN_SYS = """你是规划器。把用户目标拆成最少的有序步骤，每步一句中文短句，能独立执行。
只输出一个 JSON 字符串数组，例如 ["查北京天气", "查上海天气", "对比后给建议"]。
不要输出数组以外的任何文字。步骤控制在 5 步以内。"""

REPLAN_SYS = """你是规划器，正在修订剩余计划。
根据已完成步骤的真实结果，调整还没做的步骤：可删、可改、可加，也可原样保留。
只输出剩余步骤的 JSON 字符串数组，不要包含已完成的步骤，不要输出别的文字。
如果剩下的事都不必做了，输出空数组 []。"""


def make_plan(client: OpenAI, model: str, goal: str) -> list[str]:
    steps = _request(client, model, PLAN_SYS, f"目标：{goal}")
    return steps or []


def revise_plan(
    client: OpenAI, model: str, goal: str, done: str, remaining: list[str]
) -> list[str]:
    """改完返回新的剩余步骤；解析失败（None）就沿用旧计划，别把进度搞丢。"""
    user = f"目标：{goal}\n\n已完成：\n{done}\n\n原剩余步骤：\n" + "\n".join(
        f"- {s}" for s in remaining
    )
    steps = _request(client, model, REPLAN_SYS, user)
    return remaining if steps is None else steps


def _request(client: OpenAI, model: str, system: str, user: str) -> list[str] | None:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=400,
    )
    return _parse(resp.choices[0].message.content or "")


def _parse(text: str) -> list[str] | None:
    """返回步骤列表；空数组是合法的（没事可做），彻底解析不出返回 None。"""
    text = text.strip()
    m = re.search(r"\[.*\]", text, re.S)
    if m:
        try:
            arr = json.loads(m.group(0))
            if isinstance(arr, list):
                return [str(s).strip() for s in arr if str(s).strip()]
        except json.JSONDecodeError:
            pass
    lines = []
    for ln in text.splitlines():
        ln = re.sub(r"^\s*[-*\d.、)]+\s*", "", ln).strip()
        if ln:
            lines.append(ln)
    return lines or None
