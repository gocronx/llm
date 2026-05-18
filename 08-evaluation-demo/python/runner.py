"""runner.py —— 跑数据集评测：读 JSONL → 调 LLM → metric 判定 → 汇总。
整文件 cp 进项目即可。
"""
from __future__ import annotations

import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from openai import OpenAI

from judge import binary as judge_binary
from metrics import evaluate


@dataclass
class Result:
    sample_id: str
    category: str
    passed: bool
    pred: str
    detail: str


@dataclass
class Report:
    total: int = 0
    passed: int = 0
    by_category: dict[str, tuple[int, int]] = field(default_factory=lambda: defaultdict(lambda: (0, 0)))
    failures: list[Result] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


def load_jsonl(path: str | Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _ask(client: OpenAI, model: str, prompt: str) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0,
    )
    return resp.choices[0].message.content or ""


def run(client: OpenAI, model: str, samples: Iterable[dict],
        judge_client: OpenAI | None = None, judge_model: str | None = None,
        workers: int = 4) -> Report:
    """workers 并行调 LLM。llm_judge 类型的样本会用 judge_client/model；
    没传就退回到 client/model（自己评自己，仅 demo 用）。"""
    judge_client = judge_client or client
    judge_model = judge_model or model

    def one(s: dict) -> Result:
        pred = _ask(client, model, s["question"])
        if s["metric"] == "llm_judge":
            passed, reason = judge_binary(judge_client, judge_model, s["question"], s["rubric"], pred)
            detail = "" if passed else reason
        else:
            passed, detail = evaluate(pred, s)
        return Result(sample_id=s["id"], category=s.get("category", ""),
                      passed=passed, pred=pred, detail=detail)

    rep = Report()
    samples = list(samples)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(one, samples):
            rep.total += 1
            rep.passed += int(r.passed)
            cat_passed, cat_total = rep.by_category[r.category]
            rep.by_category[r.category] = (cat_passed + int(r.passed), cat_total + 1)
            if not r.passed:
                rep.failures.append(r)
    return rep


def print_report(rep: Report) -> None:
    print(f"\n总体：{rep.passed}/{rep.total}  通过率 {rep.pass_rate:.1%}")
    print("按分类：")
    for cat, (p, t) in sorted(rep.by_category.items()):
        print(f"  {cat:10}  {p}/{t}  {p/t:.0%}")
    if rep.failures:
        print(f"\n失败样本（{len(rep.failures)}）：")
        for r in rep.failures[:5]:
            print(f"  - [{r.sample_id}] {r.detail}")
        if len(rep.failures) > 5:
            print(f"  ... {len(rep.failures) - 5} more")
