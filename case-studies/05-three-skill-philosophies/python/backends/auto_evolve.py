"""auto_evolve.py —— hermes 模式. agent 看 transcript, 后台 LLM 写 skill.

对标 hermes-agent/run_agent.py:4077 _SKILL_REVIEW_PROMPT + skill_manage(action="create").
最小版本: 同步调用, 落盘到 .skills/auto-evolve/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from openai import OpenAI
from skills import Skill, SkillRegistry, format_skill_md, parse_skill_md

# 这段 prompt 是这个模式的灵魂. 缩短版的 hermes _SKILL_REVIEW_PROMPT.
REVIEW_PROMPT = """\
Look at the conversation above. If the user expressed a stable preference (style, format, workflow)
or you discovered a non-trivial technique, write a skill so future sessions automatically apply it.

Be ACTIVE — most useful sessions produce at least one skill. A pass that produces nothing should be the exception.

Do NOT capture:
  • Environment errors ("command not found", missing packages)
  • One-off task narratives
  • Session-specific facts

Output JSON on a single line, nothing else:
  {"action": "save", "name": "<kebab-case-slug>", "description": "<one line: when to use>", "body": "<markdown body>"}
or
  {"action": "skip", "reason": "<one short sentence>"}
"""


class AutoEvolveRegistry(SkillRegistry):
    """hermes 风格. agent 自己写 skill."""

    def __init__(self, base_dir: Path, client: OpenAI, model: str) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.client = client
        self.model = model

    def philosophy(self) -> str:
        return "self-produce"

    def list_active(self) -> list[Skill]:
        out: list[Skill] = []
        for skill_dir in sorted(self.base_dir.iterdir()):
            md = skill_dir / "SKILL.md"
            if md.is_file():
                out.append(
                    parse_skill_md(
                        md.read_text(encoding="utf-8"), fallback_name=skill_dir.name
                    )
                )
        return out

    def acquire(self, *, transcript=None, user_hint=None) -> list[Skill]:
        """对应 hermes _spawn_background_review. 后台 LLM 看完整 transcript 决定."""
        if not transcript:
            return []

        messages = list(transcript) + [
            {"role": "system", "content": REVIEW_PROMPT},
            {"role": "user", "content": "Decide now. JSON only."},
        ]
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
            )
            raw = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            print(f"  [auto-evolve] LLM 调用失败: {e}")
            return []

        # 抽 JSON. LLM 经常在 JSON 周围加 fence 或解释.
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            print(f"  [auto-evolve] LLM 没给 JSON, 跳过. 原始: {raw[:100]!r}")
            return []
        try:
            decision = json.loads(m.group(0))
        except json.JSONDecodeError:
            print(f"  [auto-evolve] JSON 解析失败: {m.group(0)[:100]!r}")
            return []

        if decision.get("action") != "save":
            print(f"  [auto-evolve] LLM 决定: skip ({decision.get('reason', '')!r})")
            return []

        name = decision["name"]
        skill = Skill(
            name=name,
            description=decision["description"],
            body=decision["body"],
            source="auto-evolved",
        )
        skill_dir = self.base_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(format_skill_md(skill), encoding="utf-8")
        print(f"  [auto-evolve] 写了 skill: {name!r} ({skill.description!r})")
        return [skill]
