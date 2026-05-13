"""Discover SKILL.md files, score relevance to a user prompt, compose into a system message."""

from __future__ import annotations

import os
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import requests
import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")

SKILLS_DIR = Path(__file__).parent / "skills"
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


def load_skills(skills_dir: Path = SKILLS_DIR) -> list[Skill]:
    skills = []
    for path in sorted(skills_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        meta = yaml.safe_load(m.group(1))
        skills.append(Skill(
            name=meta["name"],
            description=meta.get("description", ""),
            triggers=meta.get("triggers", []),
            body=m.group(2),
            path=path,
        ))
    return skills


# In-process cache keyed by (path, mtime). Re-scans only when a file changes.
_skills_cache: tuple[list[Skill], dict[str, float]] | None = None


def load_skills_cached(skills_dir: Path = SKILLS_DIR) -> list[Skill]:
    global _skills_cache
    paths = sorted(skills_dir.glob("*.md"))
    fingerprint = {str(p): p.stat().st_mtime for p in paths}
    if _skills_cache and _skills_cache[1] == fingerprint:
        return _skills_cache[0]
    skills = load_skills(skills_dir)
    _skills_cache = (skills, fingerprint)
    return skills


# ---------- Routing strategies ----------

def route_keyword(prompt: str, skills: list[Skill], top_k: int = 2) -> list[Skill]:
    """Score each skill by counting trigger keywords appearing in prompt (case-insensitive)."""
    p = prompt.lower()
    scored = []
    for s in skills:
        hits = sum(1 for t in s.triggers if t.lower() in p)
        # Description words (split on punctuation/whitespace) also count, weighted lower
        desc_words = {w.lower() for w in re.findall(r"[a-zA-Z一-鿿]{3,}", s.description)}
        hits += 0.3 * sum(1 for w in desc_words if w in p)
        if hits > 0:
            scored.append((hits, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:top_k]]


ROUTER_SYSTEM = (
    "You are a skill router. Output ONLY a JSON array of skill names, like [\"sql-query-builder\"]. "
    "No analysis, no explanation, no thinking — just the array. "
    "Pick 0 to 2 skills that match the user's domain. Be inclusive: SQL questions → sql skill, "
    "translation → translation skill, etc. Empty [] only if truly nothing matches. "
    "Your entire reply must start with [ and end with ]."
)


def _extract_json_array(text: str) -> list | None:
    """Find the LAST balanced [...] in text and try to parse it as JSON."""
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
                        return json.loads(text[start : end + 1])
                    except json.JSONDecodeError:
                        break
        if depth != 0:
            continue
    return None


def route_llm(prompt: str, skills: list[Skill], top_k: int = 2) -> list[Skill]:
    """Ask the LLM which skills are relevant."""
    catalog = "\n".join(f"- {s.name}: {s.description}" for s in skills)
    user_msg = (
        f"Skills:\n{catalog}\n\n"
        f"User prompt: {prompt}\n\n"
        f"JSON array of matching skill names (max {top_k}):"
    )
    resp = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": ROUTER_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.0,
            "max_tokens": 400,
        },
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    names = _extract_json_array(text)
    if not isinstance(names, list):
        return []
    by_name = {s.name: s for s in skills}
    return [by_name[n] for n in names if isinstance(n, str) and n in by_name][:top_k]


# ---------- Compose into messages ----------

@dataclass
class Composed:
    system: str
    loaded_skill_names: list[str]


BASE_SYSTEM = "You are a helpful assistant. Follow any loaded skill instructions strictly."


def compose(prompt: str, skills: list[Skill], mode: Literal["none", "all", "auto-keyword", "auto-llm"],
            top_k: int = 2) -> Composed:
    if mode == "none":
        return Composed(system=BASE_SYSTEM, loaded_skill_names=[])
    if mode == "all":
        loaded = skills
    elif mode == "auto-keyword":
        loaded = route_keyword(prompt, skills, top_k=top_k)
    elif mode == "auto-llm":
        loaded = route_llm(prompt, skills, top_k=top_k)
    else:
        raise ValueError(f"unknown mode: {mode}")

    if not loaded:
        return Composed(system=BASE_SYSTEM, loaded_skill_names=[])

    blocks = [BASE_SYSTEM, ""] + [s.as_system_block() for s in loaded]
    return Composed(system="\n\n".join(blocks), loaded_skill_names=[s.name for s in loaded])


# ---------- Run against LLM ----------

def call_llm(system: str, user_prompt: str, max_tokens: int = 500) -> str:
    resp = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def system_token_estimate(system: str) -> int:
    """Rough estimate: 1 token ≈ 4 chars for English, 1.5 for Chinese mix."""
    return int(len(system) / 2)


# ---------- Implicit mode: let the main LLM pick via tool call ----------
# Hermes-agent / Anthropic Skills style: list (name, description) in system prompt,
# expose skill_view(name) as a tool, let the LLM decide whether to load any body.

SKILL_VIEW_TOOL = {
    "type": "function",
    "function": {
        "name": "skill_view",
        "description": (
            "Load the full body of a skill by its name. Call this when a skill from "
            "the available_skills index seems relevant to the user's task."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill name as listed in the index"},
            },
            "required": ["name"],
        },
    },
}

IMPLICIT_SYSTEM_TEMPLATE = (
    "You are a helpful assistant. Before responding, scan the available skills below "
    "and load any that touch the user's topic.\n\n"
    "## Rules\n"
    "- If a skill's description **overlaps in topic** with the user's request, you MUST call "
    "skill_view(name) FIRST. Do not start answering until the skill is loaded.\n"
    "- Topic match is enough — do not wait for exact keywords. Synonyms, paraphrases, "
    "and indirect mentions all count.\n"
    "  * '对话录音 / 会议记录 / 语音转写' → meeting-notes-formatter\n"
    "  * '中译英 / 改成英语 / translate to English' → translation-zh-en\n"
    "  * 'schema / 索引 / 数据库表结构' → sql-query-builder\n"
    "- **Load even if the user hasn't provided concrete content yet.** "
    "If they say '审查我的代码' / '帮我翻译' / '写个查询' with no content attached, "
    "still load the skill — the skill itself tells you how to ask for the missing input. "
    "Don't decide 'this is too vague to need a skill'.\n"
    "- WRONG: mentioning a skill by name in your reply (e.g. 'I could use the X skill...') "
    "without actually calling skill_view. This is a failure.\n"
    "- WRONG: announcing loaded skills or referencing their instructions in your answer. "
    "Examples to avoid: 'I've loaded the X skill', '我已加载 X 技能', '根据 X 技能', "
    "'根据技能说明', '基于这个技能的规则', '按照 skill 的要求'. "
    "Also avoid meta-commentary like 'this is a case where ...' or '这是一个 ... 的情况' "
    "before producing the actual answer. Just answer directly.\n"
    "- WRONG: answering directly when a skill clearly applies because you 'can handle it'. "
    "The skill encodes how it should be done HERE, not just what you know in general.\n"
    "- Only skip skill_view for trivia (basic math, weather, time, definitions) or pure small talk.\n\n"
    "<available_skills>\n{index}\n</available_skills>"
)


def build_implicit_system(skills: list[Skill]) -> str:
    index = "\n".join(f"  - {s.name}: {s.description}" for s in skills)
    return IMPLICIT_SYSTEM_TEMPLATE.format(index=index)


def run_implicit(
    user_prompt: str,
    skills: list[Skill],
    max_iters: int = 3,
    max_tokens: int = 600,
) -> tuple[str, list[str]]:
    """Run a tool-using conversation. Returns (final_answer, names of loaded skills)."""
    by_name = {s.name: s for s in skills}
    messages: list[dict] = [
        {"role": "system", "content": build_implicit_system(skills)},
        {"role": "user", "content": user_prompt},
    ]
    loaded: list[str] = []

    for _ in range(max_iters):
        resp = requests.post(
            f"{API_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "model": MODEL_ID,
                "messages": messages,
                "tools": [SKILL_VIEW_TOOL],
                "temperature": 0.0,
                "max_tokens": max_tokens,
            },
            timeout=180,
        )
        resp.raise_for_status()
        msg = resp.json()["choices"][0]["message"]
        messages.append(msg)

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return (msg.get("content") or "").strip(), loaded

        for tc in tool_calls:
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            name = args.get("name", "")
            skill = by_name.get(name)
            if skill is None:
                content = f"Error: skill '{name}' not found. Available: {list(by_name)}"
            else:
                content = skill.body.strip()
                loaded.append(name)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": content,
            })

    return "[max iterations reached without final answer]", loaded


if __name__ == "__main__":
    skills = load_skills()
    print(f"loaded {len(skills)} skills:")
    for s in skills:
        print(f"  - {s.name}: {s.description}")
