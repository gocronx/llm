"""orchestrator.py —— 多 agent 编排：顺序 / 并行 / 带依赖的 DAG。
整文件 cp 进项目即可。

每个 Step：用哪个 agent 跑、跑什么 task、依赖哪些前置 step 的输出作为 context。
依赖结果会按 step.id 拼成 "id: 内容" 喂给被依赖的 step。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from agent import Agent


@dataclass
class Step:
    id: str
    agent: str
    task: str
    depends_on: list[str] = field(default_factory=list)


def _context(results: dict[str, str], deps: list[str], max_chars: int = 400) -> str:
    """把依赖 step 的输出拼成 context；过长就截断（防 LLM context 爆）。"""
    parts = []
    for d in deps:
        if d in results:
            content = results[d]
            if len(content) > max_chars:
                content = content[:max_chars] + "...(已截断)"
            parts.append(f"[{d}]\n{content}")
    return "\n\n".join(parts)


def run_sequential(agents: dict[str, Agent], workflow: list[Step]) -> dict[str, str]:
    """顺序执行；每个 step 拿到之前依赖 step 的产物作为 context。"""
    results: dict[str, str] = {}
    for step in workflow:
        agent = agents[step.agent]
        ctx = _context(results, step.depends_on)
        results[step.id] = agent.execute(step.task, ctx)
    return results


def run_parallel(agents: dict[str, Agent], steps: list[Step]) -> dict[str, str]:
    """并行执行（彼此独立的 step）。不解依赖 —— 调用方保证 steps 之间没 depends_on。"""
    results: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(steps)) as ex:
        futs = {ex.submit(agents[s.agent].execute, s.task): s for s in steps}
        for fut, s in futs.items():
            results[s.id] = fut.result()
    return results
