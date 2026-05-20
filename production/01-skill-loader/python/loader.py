"""loader.py —— 发现 + 解析 SKILL.md，缓存按 mtime 失效。整文件 cp 进项目即可。

SKILL.md 格式：YAML frontmatter（name / description / triggers）+ markdown body。
约定：name 唯一，触发关键词 triggers 是写给 keyword 路由用的，description 是给 LLM 路由
和 implicit-tool 模式读的"目录条目"。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


@dataclass
class Skill:
    name: str
    description: str
    triggers: list[str]
    body: str
    path: Path

    def as_system_block(self) -> str:
        return f"## Skill: {self.name}\n\n{self.body.strip()}"


def load_skills(skills_dir: Path) -> list[Skill]:
    skills: list[Skill] = []
    for path in sorted(skills_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        meta = yaml.safe_load(m.group(1)) or {}
        skills.append(Skill(
            name=meta["name"],
            description=meta.get("description", ""),
            triggers=meta.get("triggers", []),
            body=m.group(2),
            path=path,
        ))
    return skills


# 进程内缓存：按 (path, mtime) 指纹失效，热更新友好
_CACHE: tuple[list[Skill], dict[str, float]] | None = None


def load_skills_cached(skills_dir: Path) -> list[Skill]:
    """同 load_skills，但文件没变就走内存。生产建议加这层。"""
    global _CACHE
    paths = sorted(skills_dir.glob("*.md"))
    fp = {str(p): p.stat().st_mtime for p in paths}
    if _CACHE and _CACHE[1] == fp:
        return _CACHE[0]
    skills = load_skills(skills_dir)
    _CACHE = (skills, fp)
    return skills
