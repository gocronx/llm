"""test.py —— 不依赖 LLM 的纯逻辑测试。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from loader import load_skills, load_skills_cached
from router import _extract_array, compose, route_keyword


SAMPLE_SKILL = """---
name: test-skill
description: A test skill for translation
triggers:
  - translate
  - 翻译
---

# Body

Just translate from 中文 to English.
"""


def t(label: str, cond: bool) -> bool:
    print(f"{'✓' if cond else '✗'} {label}")
    return cond


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        dpath = Path(d)
        (dpath / "test-skill.md").write_text(SAMPLE_SKILL, encoding="utf-8")
        skills = load_skills(dpath)

        passed = sum([
            t("load_skills parses frontmatter",
              len(skills) == 1 and skills[0].name == "test-skill"
              and "翻译" in skills[0].triggers),
            t("load_skills_cached returns same on no change",
              load_skills_cached(dpath) is load_skills_cached(dpath)),

            t("route_keyword by trigger hit",
              [s.name for s in route_keyword("帮我翻译一下", skills)] == ["test-skill"]),
            t("route_keyword no match → empty",
              route_keyword("today's weather", skills) == []),

            t("compose no skills → no skill blocks",
              "## Skill:" not in compose(skills, []).system),
            t("compose with skill embeds body",
              "Body" in compose(skills, skills).system),

            t("_extract_array picks last array",
              _extract_array("garbage [\"a\"]") == ["a"]),
            t("_extract_array bad json → []",
              _extract_array("garbage no array here") == []),
        ])
    print(f"\n{passed}/8 passed")


if __name__ == "__main__":
    main()
