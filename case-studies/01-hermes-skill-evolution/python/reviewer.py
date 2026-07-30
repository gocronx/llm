"""reviewer.py —— 后台复盘 LLM 调用. 对标 hermes/run_agent.py:4312 _spawn_background_review.

跟 hermes 一比一对照:
  - hermes 的 _SKILL_REVIEW_PROMPT 在 run_agent.py:4077-4171, ~100 行
  - 我们简化到 30 行, 保留两个最关键的设计:
    1) "Be ACTIVE" 的偏置语
    2) 反例清单 (哪些事不要捕获)
  - hermes 让 LLM 调 skill_manage 工具 (action="create"/"edit"/"patch"/"write_file")
  - 我们改成让 LLM 直接输出 JSON, 主程序拿 JSON 走 skills.save()
    (没用 function calling 是因为这里目的是看清机制, 越少耦合越好)
"""
from __future__ import annotations

import json
import re

from openai import OpenAI

# 这段 prompt 是整个机制最关键的一段. hermes 的版本更长, 但精神在这.
SKILL_REVIEW_PROMPT = """\
Review the conversation above and decide if you should write a skill for future sessions.

Be ACTIVE — most useful sessions produce at least one skill update, even if small.
A pass that produces nothing should be the exception, not the default.

Signals that warrant a skill (any one is enough):
  • User corrected your style, tone, format, or verbosity ("stop doing X", "always do Y", "remember this")
  • User corrected your workflow or sequence of steps
  • A non-trivial technique, fix, or tool-usage pattern emerged worth reusing
  • An existing skill turned out to be wrong or incomplete

Do NOT capture:
  • Environment-dependent failures ("command not found", "uninstalled package")
  • Negative claims about tools ("X is broken") — these become self-imposed constraints
  • One-off task narratives ("summarize today's market", "analyze this PR")
  • Session-specific transient errors that already resolved

Respond with a JSON object on a single line, nothing else:

  {"action": "save", "name": "<kebab-case-slug>", "description": "<one line: when to use this skill>", "body": "<the skill body in markdown, including triggers and steps>"}

or

  {"action": "skip", "reason": "<one short sentence>"}

Skill name must describe a CLASS of task (e.g. "code-review-style", "weather-report-format"),
not a specific session (e.g. "fix-bug-2026-05-21" is wrong).
"""


def review(
    client: OpenAI,
    model: str,
    transcript: list[dict],
) -> dict:
    """看一份完整对话 transcript, 返回 LLM 的决定.

    transcript: 标准 OpenAI messages 列表 [{"role": ..., "content": ...}, ...]

    返回:
        {"action": "save", "name": ..., "description": ..., "body": ...}
      或 {"action": "skip", "reason": ...}
      或 {"action": "error", "raw": "<原始输出>"} —— 解析失败时
    """
    messages = list(transcript) + [
        {"role": "system", "content": SKILL_REVIEW_PROMPT},
        {"role": "user", "content": "Decide now. JSON only."},
    ]
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,  # 让它别太疯但也别太刻板
    )
    raw = (resp.choices[0].message.content or "").strip()

    # 容错: LLM 可能在 JSON 前后加点解释或 ```json fence.
    json_text = _extract_json(raw)
    if not json_text:
        return {"action": "error", "raw": raw}
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return {"action": "error", "raw": raw}


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> str | None:
    # 优先剥 fence
    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group(1)
    # 退一步, 找首个 { 到尾部最后一个 } 之间
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return None
