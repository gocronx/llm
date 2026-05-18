"""router.py —— 三种 skill 路由策略 + 组装 system message。整文件 cp 进项目即可。

route_keyword    —— 纯规则：triggers 命中数 + description 词命中（轻量加权）。0 LLM 调用。
route_llm        —— 让一个小 LLM 调用挑出相关 skill 名字。一次额外调用，更准确。
route_implicit   —— 把 skill 索引塞 system，主 LLM 自己通过 tool 调用 skill_view 加载。
                    Anthropic Skills / Hermes-agent 风格，最贴近"按需加载"。

三种各有取舍：keyword 最便宜，implicit 最贴近真"按需"但要求模型理解 tool。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

from openai import OpenAI

from loader import Skill


# ---- 关键词路由 ----

def route_keyword(prompt: str, skills: list[Skill], top_k: int = 2) -> list[Skill]:
    """trigger 全词命中 1.0，description 词命中 0.3。命中数排序取 top_k。"""
    p = prompt.lower()
    scored: list[tuple[float, Skill]] = []
    for s in skills:
        hits = sum(1 for t in s.triggers if t.lower() in p)
        desc_words = {w.lower() for w in re.findall(r"[a-zA-Z一-鿿]{3,}", s.description)}
        hits += 0.3 * sum(1 for w in desc_words if w in p)
        if hits > 0:
            scored.append((hits, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:top_k]]


# ---- LLM 路由 ----

_ROUTER_SYS = (
    "你是 skill 路由器。只输出 JSON 数组，例如 [\"sql-query-builder\"]。"
    "不要任何解释。挑 0-2 个和用户领域相关的 skill。完全没匹配就 []。"
)


def _extract_array(text: str) -> list:
    """从模型回复里抠出最后一个合法 [...] JSON 数组。模型经常给一堆解释 + 数组。"""
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


def route_llm(client: OpenAI, model: str, prompt: str, skills: list[Skill],
              top_k: int = 2) -> list[Skill]:
    catalog = "\n".join(f"- {s.name}: {s.description}" for s in skills)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _ROUTER_SYS},
            {"role": "user", "content": f"Skills:\n{catalog}\n\nPrompt: {prompt}\n\nJSON 数组（最多 {top_k}）："},
        ],
        temperature=0,
        max_tokens=200,
    )
    names = _extract_array(resp.choices[0].message.content or "")
    by_name = {s.name: s for s in skills}
    return [by_name[n] for n in names if isinstance(n, str) and n in by_name][:top_k]


# ---- 组装 system ----

@dataclass
class Composed:
    system: str
    loaded: list[str]


BASE_SYSTEM = "你是助手。严格遵循已加载 skill 的说明。"


def compose(skills: list[Skill], loaded: list[Skill]) -> Composed:
    if not loaded:
        return Composed(BASE_SYSTEM, [])
    blocks = [BASE_SYSTEM, ""] + [s.as_system_block() for s in loaded]
    return Composed("\n\n".join(blocks), [s.name for s in loaded])


# ---- Implicit：让主 LLM 通过 tool 自己加载 ----

SKILL_VIEW_TOOL = {
    "type": "function",
    "function": {
        "name": "skill_view",
        "description": "按 name 加载一个 skill 的完整正文。需要时就调，不需要不要调。",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
}

_IMPLICIT_TPL = (
    "你是助手。下面是可加载的 skill 列表，每个有 name 和简介。\n"
    "规则：用户问题和某个 skill 的主题相关时，先 call skill_view(name) 加载它，再回答。\n"
    "不要在回答里提到'我加载了 X skill'之类的元话术；直接给答案。\n"
    "完全无关的小问题（小学算术、天气、时间）不用调。\n\n"
    "<available_skills>\n{idx}\n</available_skills>"
)


def build_implicit_system(skills: list[Skill]) -> str:
    return _IMPLICIT_TPL.format(idx="\n".join(f"  - {s.name}: {s.description}" for s in skills))


def run_implicit(client: OpenAI, model: str, prompt: str, skills: list[Skill],
                 max_iters: int = 3) -> tuple[str, list[str]]:
    """让主 LLM 通过 skill_view tool 自己决定加载哪些 skill。"""
    by_name = {s.name: s for s in skills}
    messages: list[dict] = [
        {"role": "system", "content": build_implicit_system(skills)},
        {"role": "user", "content": prompt},
    ]
    loaded: list[str] = []
    for _ in range(max_iters):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=[SKILL_VIEW_TOOL],
            temperature=0, max_tokens=600,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return (msg.content or "").strip(), loaded
        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            name = args.get("name", "")
            skill = by_name.get(name)
            content = skill.body.strip() if skill else f"Error: skill '{name}' not found"
            if skill:
                loaded.append(name)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
    return "(max iterations reached)", loaded
