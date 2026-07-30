"""skills.py —— 共用的 skill 数据结构 + 抽象基类 SkillRegistry.

三种后端 (auto_evolve / forage / curated) 都实现 SkillRegistry 这同一套接口,
main.py 不知道底层是哪种哲学.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Skill:
    """一份 skill = markdown 内容 + 元数据."""

    name: str  # kebab-case 唯一 id
    description: str  # 一行: 什么时候用我
    body: str  # 主体 markdown
    source: str = "unknown"  # "auto-evolved" / "foraged-from-X" / "curated-by-Y"
    score: float = 0.0  # 采集模式才有意义
    signed_by: Optional[str] = None  # 策展模式才有意义


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_skill_md(text: str, fallback_name: str = "") -> Skill:
    """从 SKILL.md 文本解析 Skill."""
    text = text.strip()
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return Skill(name=fallback_name, description="", body=text)
    fm, body = m.group(1), m.group(2).strip()
    fields = {}
    for line in fm.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip()
    return Skill(
        name=fields.get("name", fallback_name),
        description=fields.get("description", ""),
        body=body,
        source=fields.get("source", "unknown"),
        score=float(fields.get("score", 0.0)),
        signed_by=fields.get("signed_by") or None,
    )


def format_skill_md(s: Skill) -> str:
    """对应的反序列化."""
    lines = [
        "---",
        f"name: {s.name}",
        f"description: {s.description}",
        f"source: {s.source}",
    ]
    if s.score:
        lines.append(f"score: {s.score}")
    if s.signed_by:
        lines.append(f"signed_by: {s.signed_by}")
    lines.append("---")
    lines.append("")
    lines.append(s.body.strip())
    lines.append("")
    return "\n".join(lines)


# ── 抽象基类 ──────────────────────────────────────────────────────────
class SkillRegistry(ABC):
    """三种哲学共享的接口. 业务代码 (agent) 只跟它打交道."""

    @abstractmethod
    def list_active(self) -> list[Skill]:
        """当前已加载的 skill."""
        ...

    @abstractmethod
    def acquire(
        self,
        *,
        transcript: Optional[list[dict]] = None,
        user_hint: Optional[str] = None,
    ) -> list[Skill]:
        """让 registry 去 "获取新 skill". 三种后端实现各自不同:
          - 自产: 看 transcript, 产 markdown
          - 采集: 扫 catalog, 评分挑选
          - 策展: 用 user_hint 查 catalog, 列候选给人选

        返回这次新加进来的 skill 列表 (可能为空).
        """
        ...

    @abstractmethod
    def philosophy(self) -> str:
        """返回 'self-produce' / 'forage' / 'curated', 给 demo 标签用."""
        ...

    def build_system_prompt(self) -> str:
        """通用: 把活跃 skill 拼成 system prompt 段."""
        active = self.list_active()
        if not active:
            return ""
        lines = ["## Skills available", ""]
        for s in active:
            tag = f"[{s.source}]"
            lines.append(f"- **{s.name}** {tag} — {s.description}")
        lines.append("")
        lines.append("Skills with full content:")
        for s in active:
            lines.append(f"\n### {s.name}\n{s.body}\n")
        return "\n".join(lines)
