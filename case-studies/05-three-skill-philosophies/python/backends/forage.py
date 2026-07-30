"""forage.py —— zeroclaw 模式. 从外部 catalog 扫候选, 评分, 自动安装高分的.

对标 zeroclaw/crates/zeroclaw-runtime/src/skillforge/ (scout / evaluate / integrate).
最小版本: catalog 是本地目录 (模拟远程 catalog), 评分是简单加权.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from skills import Skill, SkillRegistry, format_skill_md, parse_skill_md


@dataclass
class ForageConfig:
    """采集策略.

    score_threshold: 高于这个分自动装. 低的扔.
    max_per_acquire: 一次最多装几个 (防 catalog 突然增加 100 个把库塞满).
    """

    score_threshold: float = 0.6
    max_per_acquire: int = 3


class ForageRegistry(SkillRegistry):
    """zeroclaw 风格. scout catalog → evaluate → integrate."""

    def __init__(
        self,
        catalog_dir: Path,
        installed_dir: Path,
        config: Optional[ForageConfig] = None,
    ) -> None:
        self.catalog_dir = catalog_dir  # 模拟外部 catalog (本地目录)
        self.installed_dir = installed_dir
        self.installed_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or ForageConfig()

    def philosophy(self) -> str:
        return "forage"

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

    # ── 三步: scout → evaluate → integrate ────────────────────────────
    def _scout(self) -> list[Skill]:
        """扫 catalog 目录, 返回所有候选."""
        if not self.catalog_dir.exists():
            return []
        candidates: list[Skill] = []
        for f in sorted(self.catalog_dir.glob("*.md")):
            s = parse_skill_md(f.read_text(encoding="utf-8"), fallback_name=f.stem)
            candidates.append(s)
        return candidates

    def _evaluate(self, candidates: list[Skill]) -> list[tuple[Skill, float]]:
        """给每个候选打分. 真 zeroclaw 综合来源信誉 / 安装数 / 安全审计.
        Demo 简化: 直接读 catalog 文件里 frontmatter 的 score 字段."""
        return [(s, s.score) for s in candidates]

    def _integrate(self, ranked: list[tuple[Skill, float]]) -> list[Skill]:
        """把分高且不冲突的装上."""
        already_installed = {s.name for s in self.list_active()}
        installed_now: list[Skill] = []
        for skill, score in sorted(ranked, key=lambda x: -x[1]):
            if len(installed_now) >= self.config.max_per_acquire:
                break
            if score < self.config.score_threshold:
                print(
                    f"  [forage] 跳过 {skill.name!r} (score {score:.2f} < threshold {self.config.score_threshold})"
                )
                continue
            if skill.name in already_installed:
                continue
            skill_dir = self.installed_dir / skill.name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                format_skill_md(skill), encoding="utf-8"
            )
            installed_now.append(skill)
            print(
                f"  [forage] 装 {skill.name!r} (score={score:.2f}, 来源={skill.source})"
            )
        return installed_now

    def acquire(self, *, transcript=None, user_hint=None) -> list[Skill]:
        """一次完整 scout → evaluate → integrate."""
        candidates = self._scout()
        if not candidates:
            print(f"  [forage] catalog 是空的 ({self.catalog_dir})")
            return []
        print(f"  [forage] scout 到 {len(candidates)} 个候选")
        ranked = self._evaluate(candidates)
        return self._integrate(ranked)
