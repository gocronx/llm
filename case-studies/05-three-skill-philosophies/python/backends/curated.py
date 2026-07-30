"""curated.py —— ironclaw 模式. 只允许装提前 "签名" 过的 skill, 拒绝其它.

对标 ironclaw/src/tools/builtin/skill_tools.rs (skill_install) +
ironclaw/wit/tool.wit (host capability 白名单).
最小版本: approved_dir 是 "人审过" 的 skill 集合, 装的时候验签 (这里简化为 signed_by 字段).
没真接 WASM, 把"沙盒"概念落到 "只能调白名单 API" 上.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from skills import Skill, SkillRegistry, format_skill_md, parse_skill_md

# ironclaw WIT 接口里的能力清单 (wit/tool.wit:18-106) 缩略版.
# 装载 skill 时, skill 在 body 里申请的能力如果不在这白名单里, 拒装.
ALLOWED_CAPABILITIES = {
    "workspace-read",
    "workspace-write",
    "log",
    "http-request",
    "tool-invoke",
    "secret-exists",
}

# 信任的签名者集合. 真 ironclaw 用 sigstore / minisign 等.
# Demo: 简单地白名单几个 ID.
TRUSTED_SIGNERS = {"ironclaw-team", "verified-author-1"}


class CuratedRegistry(SkillRegistry):
    """ironclaw 风格. 只装签名过的 skill, 拒绝其它来源."""

    def __init__(self, approved_dir: Path, installed_dir: Path) -> None:
        self.approved_dir = approved_dir
        self.installed_dir = installed_dir
        self.installed_dir.mkdir(parents=True, exist_ok=True)

    def philosophy(self) -> str:
        return "curated"

    def list_active(self) -> list[Skill]:
        out: list[Skill] = []
        for skill_dir in sorted(self.installed_dir.iterdir()):
            md = skill_dir / "SKILL.md"
            if md.is_file():
                out.append(
                    parse_skill_md(
                        md.read_text(encoding="utf-8"), fallback_name=skill_dir.name
                    )
                )
        return out

    def list_available(self) -> list[Skill]:
        """skill_search 等价物. 列出 approved catalog 里所有可装的."""
        if not self.approved_dir.exists():
            return []
        out: list[Skill] = []
        for f in sorted(self.approved_dir.glob("*.md")):
            out.append(
                parse_skill_md(f.read_text(encoding="utf-8"), fallback_name=f.stem)
            )
        return out

    def install(self, name: str) -> Optional[Skill]:
        """手动装某个 skill, 走完整签名 / 能力检查."""
        avail = {s.name: s for s in self.list_available()}
        if name not in avail:
            print(f"  [curated] 拒装: {name!r} 不在 approved catalog 里")
            return None
        s = avail[name]

        # 验签
        if s.signed_by not in TRUSTED_SIGNERS:
            print(
                f"  [curated] 拒装: signed_by={s.signed_by!r} 不在信任列表 {TRUSTED_SIGNERS}"
            )
            return None

        # 检查 skill 申请的能力 (扫 body 里的 capability 标记)
        requested = self._extract_capabilities(s.body)
        unauthorized = requested - ALLOWED_CAPABILITIES
        if unauthorized:
            print(f"  [curated] 拒装: skill 申请了未授权能力 {unauthorized}")
            return None

        # 通过, 装上
        skill_dir = self.installed_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(format_skill_md(s), encoding="utf-8")
        cap_str = ", ".join(sorted(requested)) if requested else "(none)"
        print(
            f"  [curated] 装 {name!r}, signed_by={s.signed_by}, capabilities=[{cap_str}]"
        )
        return s

    def _extract_capabilities(self, body: str) -> set[str]:
        """从 skill body 里抓 'capabilities: [...]' 行的简单格式.
        真 ironclaw 是 WIT 编译时验证 imports.
        """
        m = re.search(r"capabilities:\s*\[([^\]]*)\]", body)
        if not m:
            return set()
        return {c.strip() for c in m.group(1).split(",") if c.strip()}

    def acquire(self, *, transcript=None, user_hint=None) -> list[Skill]:
        """策展模式不自动装. 给个提示让人选."""
        avail = self.list_available()
        active_names = {s.name for s in self.list_active()}
        installable = [s for s in avail if s.name not in active_names]
        if not installable:
            print(f"  [curated] catalog 没有新候选 (已装: {sorted(active_names)})")
            return []

        # 如果 user_hint 明确指定要装哪个, 走 install
        if user_hint:
            target = user_hint.strip()
            if any(s.name == target for s in installable):
                installed = self.install(target)
                return [installed] if installed else []
            print(f"  [curated] user_hint={target!r} 未在 catalog 中找到")
            return []

        # 没 hint, 不自动装, 列候选供观察
        print("  [curated] 可装的 (需用户 hint 才装):")
        for s in installable:
            sig = f"signed_by={s.signed_by!r}" if s.signed_by else "未签名"
            print(f"      - {s.name}  [{sig}]  {s.description}")
        return []
