"""test.py —— 用 mock agent 测 orchestrator 的依赖传递和并行。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orchestrator import Step, run_parallel, run_sequential


@dataclass
class FakeAgent:
    name: str
    role: str = "fake"

    def execute(self, task: str, context: str = "") -> str:
        return f"[{self.name}] task={task} ctx={context!r}"


def test_sequential_context_propagation() -> bool:
    a = {"w": FakeAgent("writer"), "r": FakeAgent("reviewer"), "e": FakeAgent("editor")}
    wf = [
        Step("draft",  "w", "写"),
        Step("review", "r", "审", depends_on=["draft"]),
        Step("final",  "e", "改", depends_on=["draft", "review"]),
    ]
    res = run_sequential(a, wf)
    # editor 应该看到 draft 和 review 的内容
    ok = "[draft]" in res["final"] and "[review]" in res["final"]
    print(f"{'✓' if ok else '✗'} sequential context propagation")
    return ok


def test_parallel_runs_all() -> bool:
    a = {"w": FakeAgent("writer")}
    steps = [Step(f"s{i}", "w", f"t{i}") for i in range(5)]
    res = run_parallel(a, steps)
    ok = len(res) == 5 and all(f"s{i}" in res for i in range(5))
    print(f"{'✓' if ok else '✗'} parallel runs all 5 steps")
    return ok


def test_context_truncation() -> bool:
    a = {"w": FakeAgent("w")}
    res1 = a["w"].execute("step1")
    # 直接造一个超长的依赖输出
    results = {"draft": "x" * 1000}
    from orchestrator import _context
    ctx = _context(results, ["draft"], max_chars=100)
    ok = len(ctx) < 200 and "已截断" in ctx
    print(f"{'✓' if ok else '✗'} context truncation kicks in")
    return ok


def main() -> None:
    passed = sum([
        test_sequential_context_propagation(),
        test_parallel_runs_all(),
        test_context_truncation(),
    ])
    print(f"\n{passed}/3 passed")


if __name__ == "__main__":
    main()
