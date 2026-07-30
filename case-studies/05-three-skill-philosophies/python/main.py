"""main.py —— 4 个场景, 同一抽象, 三种哲学跑出三种结果.

设计意图: SkillRegistry 抽象基类让 4 个场景**不知道**底层用的是哪种哲学.
切换哲学 = 换一个 Registry 实现, 业务逻辑零改动. (这是 case 03 多后端模式的延伸)
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import httpx
from backends.auto_evolve import AutoEvolveRegistry
from backends.curated import CuratedRegistry
from backends.forage import ForageConfig, ForageRegistry
from dotenv import load_dotenv
from openai import OpenAI

# python/ 在 sys.path 头部, 直接 import 没问题
from skills import SkillRegistry

load_dotenv()

HERE = Path(__file__).parent
SKILLS_ROOT = HERE / ".skills"
AUTO_EVOLVE_DIR = SKILLS_ROOT / "auto-evolve"
FORAGE_INSTALLED = SKILLS_ROOT / "foraged"
CURATED_INSTALLED = SKILLS_ROOT / "curated"
CATALOG_DIR = HERE / "fixtures" / "catalog"
APPROVED_DIR = HERE / "fixtures" / "approved"


def _make_client() -> tuple[OpenAI, str]:
    http = httpx.Client(trust_env=False, timeout=60.0)
    client = OpenAI(
        base_url=os.environ["API_BASE_URL"],
        api_key=os.environ.get("API_KEY", "not-needed"),
        http_client=http,
    )
    return client, os.environ["MODEL_ID"]


def _print_section(title: str) -> None:
    print(f"\n{'=' * 64}\n{title}\n{'=' * 64}")


def _reset() -> None:
    if SKILLS_ROOT.exists():
        shutil.rmtree(SKILLS_ROOT)


# ── 场景 1 · 三种 registry 各自的 acquire 表现 ────────────────────────
def scenario_three_acquires() -> None:
    _print_section("场景 1 · 三种 acquire 同时跑, 看产出有什么不同")

    _reset()
    client, model = _make_client()

    # 模拟一段简短的对话, 给 auto-evolve 用
    transcript = [
        {"role": "system", "content": "你是简洁代码助手."},
        {"role": "user", "content": "写一个调外部 API 的客户端"},
        {"role": "assistant", "content": "好, 给你一个最小版本: ..."},
        {"role": "user", "content": "请加 rate-limit + retry. 以后写所有 API 客户端都这样, 别每次问我."},
        {"role": "assistant", "content": "明白. 这次的版本加上 token bucket 限速 + 指数退避 retry: ..."},
    ]

    registries: dict[str, SkillRegistry] = {
        "auto-evolve": AutoEvolveRegistry(AUTO_EVOLVE_DIR, client, model),
        "forage": ForageRegistry(CATALOG_DIR, FORAGE_INSTALLED),
        "curated": CuratedRegistry(APPROVED_DIR, CURATED_INSTALLED),
    }

    for label, reg in registries.items():
        print(f"\n[{label} · 哲学={reg.philosophy()}]")
        acquired = reg.acquire(transcript=transcript, user_hint=None)
        print(f"  本次 acquire 得到 {len(acquired)} 个 skill")

    print(f"\n各自当前装着的 skill:")
    for label, reg in registries.items():
        active = reg.list_active()
        names = [s.name for s in active]
        print(f"  {label}: {names}")


# ── 场景 2 · forage 评分阈值过滤 ──────────────────────────────────────
def scenario_forage_threshold() -> None:
    _print_section("场景 2 · forage 评分阈值过滤")

    _reset()
    # 默认阈值 0.6, catalog 里有一个 0.32 分的烂 skill, 应该被刷掉
    reg = ForageRegistry(CATALOG_DIR, FORAGE_INSTALLED, ForageConfig(score_threshold=0.6))
    print(f"score_threshold = 0.6")
    print(f"catalog 里有 {len(list(CATALOG_DIR.glob('*.md')))} 个候选\n")

    reg.acquire()

    active = reg.list_active()
    print(f"\n装上的 skill ({len(active)} 个):")
    for s in active:
        print(f"  - {s.name} (score={s.score})")
    print("→ 0.32 分的低质量 skill 被刷掉了 ✓")

    # 把阈值降到 0.3 再装, 看会不会装上烂 skill
    print(f"\n现在降阈值到 0.2, 重装一次:")
    _reset()
    reg2 = ForageRegistry(CATALOG_DIR, FORAGE_INSTALLED, ForageConfig(score_threshold=0.2, max_per_acquire=10))
    reg2.acquire()
    active2 = reg2.list_active()
    print(f"\n装上的 skill ({len(active2)} 个):")
    for s in active2:
        print(f"  - {s.name} (score={s.score})")
    print("→ 阈值降下来后, 烂 skill 也装上了 (调参的脆弱性) ⚠️")


# ── 场景 3 · curated 拒装规则全套 ─────────────────────────────────────
def scenario_curated_rejections() -> None:
    _print_section("场景 3 · curated 模式: 拒装的几种情况")

    _reset()
    reg = CuratedRegistry(APPROVED_DIR, CURATED_INSTALLED)

    print("approved catalog 里有这些 (含一个未签名的诱饵):\n")
    for s in reg.list_available():
        sig = f"signed_by={s.signed_by!r}" if s.signed_by else "**未签名**"
        print(f"  - {s.name}  [{sig}]")

    print(f"\n[尝试 1] 装 secure-file-write (合法)")
    reg.install("secure-file-write")

    print(f"\n[尝试 2] 装 sketchy-skill-unsigned (无签名)")
    reg.install("sketchy-skill-unsigned")

    print(f"\n[尝试 3] 装 nonexistent (catalog 里没有)")
    reg.install("nonexistent")

    print(f"\n[尝试 4] 装 http-client-best-practices (合法)")
    reg.install("http-client-best-practices")

    print(f"\n最终装上的:")
    for s in reg.list_active():
        print(f"  - {s.name}  signed_by={s.signed_by}")
    print(f"\n→ 4 次尝试, 2 个通过 (有签名), 2 个被拒 (无签名 / 不存在) ✓")


# ── 场景 4 · 三种 registry 同时给同一个新任务, 看 system prompt 差异 ────
def scenario_compare_system_prompts() -> None:
    _print_section("场景 4 · 同样 user_hint, 三种 registry 给出的 system prompt 长啥样")

    _reset()
    client, model = _make_client()

    # 各自先 acquire 一次, 用 demo 准备的 input
    transcript = [
        {"role": "user", "content": "以后写 JSON 都 indent=2 sort_keys=True, 别老搞紧凑格式."},
        {"role": "assistant", "content": "记住了."},
    ]

    auto = AutoEvolveRegistry(AUTO_EVOLVE_DIR, client, model)
    forage = ForageRegistry(CATALOG_DIR, FORAGE_INSTALLED)
    curated = CuratedRegistry(APPROVED_DIR, CURATED_INSTALLED)

    print("[acquire 阶段]")
    print("\nauto-evolve:")
    auto.acquire(transcript=transcript)
    print("\nforage:")
    forage.acquire()
    print("\ncurated (hint=http-client-best-practices):")
    curated.acquire(user_hint="http-client-best-practices")

    print("\n\n=== 三种 registry 此刻 build_system_prompt() 的输出长度对比 ===\n")
    for label, reg in [("auto", auto), ("forage", forage), ("curated", curated)]:
        sp = reg.build_system_prompt()
        names = [s.name for s in reg.list_active()]
        print(f"  {label}: {len(names)} skill, prompt 长度 {len(sp)} 字符. names={names}")

    print("\n[抽样: auto-evolve 注入的 prompt 头几行]")
    print(_indent(auto.build_system_prompt()[:300], "    "))
    print("\n[抽样: forage 注入的 prompt 头几行]")
    print(_indent(forage.build_system_prompt()[:300], "    "))
    print("\n[抽样: curated 注入的 prompt 头几行]")
    print(_indent(curated.build_system_prompt()[:300], "    "))


def _indent(s: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in s.splitlines())


# ── main ──────────────────────────────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", type=int, choices=[1, 2, 3, 4])
    p.add_argument("--cleanup", action="store_true", help="清理 .skills/")
    args = p.parse_args()

    if args.cleanup:
        _reset()
        print(f"已清理 {SKILLS_ROOT}")
        return

    scenarios = {
        1: scenario_three_acquires,
        2: scenario_forage_threshold,
        3: scenario_curated_rejections,
        4: scenario_compare_system_prompts,
    }

    if args.scenario:
        scenarios[args.scenario]()
    else:
        for n in sorted(scenarios):
            scenarios[n]()

    _print_section("结束")
    print(f"skill 残留 (若有): {SKILLS_ROOT}")
    print("清理: python main.py --cleanup")


if __name__ == "__main__":
    main()
