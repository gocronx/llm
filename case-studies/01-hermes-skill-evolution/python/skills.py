"""skills.py —— skill 文件的读写。markdown + YAML frontmatter，对标 hermes 的 SKILL.md 格式。

只做四件事:
  1. 列举所有 skill (返回 name+description 索引)
  2. 读单个 skill 的全文
  3. 写一个新 skill / 覆盖现有 skill
  4. 把 skill 列表拼成 system prompt 片段
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

# skill 库的位置。demo 故意放本目录下，方便观察 / 清理。
# 真 hermes 用 ~/.hermes/skills/, 但路径决策跟机制无关。
SKILLS_DIR = Path(__file__).parent / ".skills"


# ── 数据结构 ──────────────────────────────────────────────────────────
@dataclass
class Skill:
    """一个 skill 等于一份 markdown 文档."""

    name: str  # 用作目录名 / 唯一 id（kebab-case）
    description: str  # 一行话，决定下次什么场景下 LLM 会去读全文
    body: str  # SKILL.md 的正文 markdown


# ── frontmatter 解析 ──────────────────────────────────────────────────
_FRONTMATTER_RE = re.compile(
    r"^---\n(.*?)\n---\n(.*)$",
    re.DOTALL,
)


def _parse_skill_md(text: str) -> tuple[str, str]:
    """返回 (description, body). 解析失败时 description 为空."""
    m = _FRONTMATTER_RE.match(text.strip())
    if not m:
        return "", text
    fm, body = m.group(1), m.group(2)
    description = ""
    for line in fm.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            if k.strip() == "description":
                description = v.strip()
    return description, body.strip()


def _format_skill_md(description: str, body: str) -> str:
    """对应的写出格式. 始终把 description 放进 frontmatter."""
    safe_desc = description.replace("\n", " ").strip()
    return f"---\ndescription: {safe_desc}\n---\n\n{body.strip()}\n"


# ── CRUD ──────────────────────────────────────────────────────────────
def load_all() -> list[Skill]:
    """扫整个 skill 库. 用于建索引."""
    if not SKILLS_DIR.exists():
        return []
    out: list[Skill] = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8")
        desc, body = _parse_skill_md(text)
        out.append(Skill(name=skill_dir.name, description=desc, body=body))
    return out


def load_one(name: str) -> Skill | None:
    """LLM 调 skill_view 时用这个."""
    skill_md = SKILLS_DIR / name / "SKILL.md"
    if not skill_md.is_file():
        return None
    text = skill_md.read_text(encoding="utf-8")
    desc, body = _parse_skill_md(text)
    return Skill(name=name, description=desc, body=body)


def save(name: str, description: str, body: str) -> Path:
    """create 或 overwrite. 返回写入的文件路径."""
    skill_dir = SKILLS_DIR / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(_format_skill_md(description, body), encoding="utf-8")
    return skill_md


def clear() -> None:
    """demo 用. 把整个 skill 库删干净, 模拟首次启动."""
    if SKILLS_DIR.exists():
        shutil.rmtree(SKILLS_DIR)


# ── 装载到 system prompt ──────────────────────────────────────────────
def build_skills_system_prompt() -> str:
    """对标 hermes/agent/prompt_builder.py:988 的 build_skills_system_prompt.

    返回索引模式: 只放 name + description, 不放正文.
    全文要靠 skill_view 工具按需读 (本 demo 简化, 直接把全文也喂进去, 见 main.py).
    """
    skills = load_all()
    if not skills:
        return ""
    lines = ["## Skills you've learned in past sessions", ""]
    for s in skills:
        lines.append(f"- **{s.name}** — {s.description}")
    lines.append("")
    lines.append(
        "When a user's request fits one of these, follow the skill. "
        "Skills are accumulated user preferences and procedures from prior sessions."
    )
    return "\n".join(lines)
