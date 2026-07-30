"""orchestrator.py —— Subagent 编排: 主 agent 把任务拆给多个 subagent 并行执行, 再聚合结果.

灵感:
- Claude Code 的 `Task` tool (subagent_type 参数 → 起 subagent)
- PraisonAI multi-agent 框架
- AutoGPT delegate 模式

跟 H21 / H22 解决的问题不同:
- H21/H22: 单 agent context 长跑下不崩
- H23: 多 agent **并行**, 把大任务拆成独立子任务

## 核心价值

一个 agent 干一切的局限:
1. **context 污染**: 调研 task A 时上下文塞满 task A 信息, 切到 task B 必须切 context
2. **顺序执行**: A → B → C 串行, 时间是 sum, 不是 max
3. **scope creep**: 一个 prompt 想干 5 件事, LLM 容易忘前面的

Subagent 编排解决:
- **隔离 context**: 每个 subagent 自己的 messages 历史, 不污染主 agent
- **并行执行**: A, B, C 同时跑 (asyncio.gather), 时间 ≈ max(A, B, C)
- **聚合结果**: 主 agent 只看 subagent 返回的摘要, context 干净

## 主 agent vs subagent 协议

主 agent 调一个 `delegate_to_subagent` 工具:
```
{
  "subagent_type": "researcher",    # 哪种 agent
  "task": "search competitors for X", # 任务描述 (subagent 看到的唯一输入)
  "tools_allowed": ["web_search", "read_file"]  # 限制子 agent 能用的工具
}
```

Subagent 完成后, 返回一个**结构化 summary** (而不是 raw messages history):
```
{
  "status": "completed" | "failed" | "partial",
  "summary": "...",     # 主 agent 看到的
  "artifacts": {...}    # 可选附件 (e.g. 找到的 URL 列表)
}
```

主 agent 只看 summary, **不接 subagent 的完整对话** —— 这是 context 隔离的关键.

## 跟 ReAct 的关系

主 agent 自己也是 ReAct loop. `delegate_to_subagent` 只是一个特殊工具 (跟 `read_file` 一样).
区别: 这个工具内部启动一个完整 ReAct loop (子 agent), 返回时只给 summary.

```
   Main Agent's ReAct loop:
     while not done:
       LLM(主 agent prompt + tools)
         → tool: delegate_to_subagent(researcher, "search X")
                   ↓
                   Sub Agent's ReAct loop (隔离 context):
                     while not done:
                       LLM(sub prompt + sub tools)
                         → tool: web_search(...)
                     return summary
         ← summary
       继续主 agent loop
```

## 并行模式

`delegate_to_subagent` 阻塞太慢. 真生产用 `delegate_to_subagents` (复数), 一次发起 N 个并行子任务:

```python
results = await asyncio.gather(
    run_subagent("researcher", "find competitors"),
    run_subagent("researcher", "find pricing"),
    run_subagent("analyst", "summarize previous reports"),
)
# 时间 ≈ max(3 个), 不是 sum
```

## 教学版做什么

1. `SubAgent` 类: 一个 ReAct loop 简化版 (单工具, 单 prompt)
2. `Orchestrator` 类: 维护多个 SubAgent 类型, 提供 `delegate` 和 `delegate_parallel`
3. Mock LLM 演示主 + 子 agent 协作
4. `asyncio.gather` 并行 vs 串行的时间对比
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any

from models import SubAgentResult

# ---------------- SubAgent ----------------


class SubAgent:
    """简化版 ReAct loop. 接一个任务字符串, 返回结构化结果.

    设计要点:
    - 每个 SubAgent 实例有自己的 messages, 不跟其他 agent 共享
    - 完成后只导出 summary, 不导出 messages
    - 工具集是受限的 (`tools_allowed`)
    """

    def __init__(
        self,
        agent_type: str,
        llm_call: Callable[[list[dict], list[dict]], dict],
        tool_registry: dict[str, Callable[..., Any]],
        tool_schemas: dict[str, dict],
        max_iterations: int = 10,
        system_prompt: str | None = None,
    ) -> None:
        self.agent_type = agent_type
        self.llm_call = llm_call
        self.tools = tool_registry
        self.schemas = tool_schemas
        self.max_iterations = max_iterations
        self.system_prompt = (
            system_prompt
            or f"You are a {agent_type} subagent. Complete the task and report back."
        )

    async def run(
        self, task: str, tools_allowed: list[str] | None = None
    ) -> SubAgentResult:
        """跑一次完整 ReAct loop, 输出 summary."""
        t0 = time.perf_counter()
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]
        allowed = (
            tools_allowed if tools_allowed is not None else list(self.tools.keys())
        )
        sub_schemas = [self.schemas[t] for t in allowed if t in self.schemas]

        artifacts: dict[str, Any] = {}
        iter_count = 0
        last_content = ""

        for i in range(self.max_iterations):
            iter_count = i + 1
            try:
                # 用 asyncio.to_thread 把 sync llm_call 丢到 thread pool, 这样多个 subagent
                # 在 asyncio.gather 里能真并发 (不受 GIL 限制, OpenAI client 是 IO-bound).
                # mock llm 也能照常工作, 只是多 1 次 thread switch.
                resp = await asyncio.to_thread(self.llm_call, messages, sub_schemas)
            except Exception as e:
                return SubAgentResult(
                    status="failed",
                    summary="",
                    n_iterations=iter_count,
                    elapsed_ms=(time.perf_counter() - t0) * 1000,
                    error=str(e),
                )

            last_content = resp.get("content") or ""
            tool_calls = resp.get("tool_calls") or []

            if not tool_calls:
                # LLM 给出最终 content, 结束
                return SubAgentResult(
                    status="completed",
                    summary=last_content,
                    artifacts=artifacts,
                    n_iterations=iter_count,
                    elapsed_ms=(time.perf_counter() - t0) * 1000,
                )

            messages.append(
                {"role": "assistant", "tool_calls": tool_calls, "content": last_content}
            )

            for tc in tool_calls:
                name = tc["function"]["name"]
                if name not in allowed:
                    result = (
                        f"[tool '{name}' not allowed for {self.agent_type} subagent]"
                    )
                else:
                    try:
                        args = json.loads(tc["function"]["arguments"] or "{}")
                        result = str(self.tools[name](**args))
                    except Exception as e:
                        result = f"[tool error: {e}]"

                # subagent 收集 artifact: 工具名 → 结果片段
                artifacts.setdefault(name, []).append(result[:200])

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": name,
                        "content": result,
                    }
                )

        # 跑满 max_iterations 都没给 content, 退化为 "partial"
        return SubAgentResult(
            status="partial",
            summary=last_content
            or f"(reached max_iterations={self.max_iterations} without final answer)",
            artifacts=artifacts,
            n_iterations=iter_count,
            elapsed_ms=(time.perf_counter() - t0) * 1000,
        )


# ---------------- Orchestrator ----------------


class Orchestrator:
    """主 agent 用的编排器. 注册多种 subagent_type, 提供单发/并行 delegate."""

    def __init__(self) -> None:
        self._registry: dict[str, SubAgent] = {}

    def register(self, agent_type: str, subagent: SubAgent) -> None:
        self._registry[agent_type] = subagent

    async def delegate(
        self,
        agent_type: str,
        task: str,
        tools_allowed: list[str] | None = None,
    ) -> SubAgentResult:
        """单发 subagent 任务. 主 agent 一次只调一个."""
        if agent_type not in self._registry:
            return SubAgentResult(
                status="failed",
                summary="",
                error=f"unknown subagent_type: {agent_type}; available: {list(self._registry)}",
            )
        return await self._registry[agent_type].run(task, tools_allowed=tools_allowed)

    async def delegate_parallel(
        self,
        requests: list[tuple[str, str]],  # [(agent_type, task), ...]
        tools_allowed_per: list[list[str] | None] | None = None,
    ) -> list[SubAgentResult]:
        """并行发起多个 subagent. 时间 ≈ max(各 subagent), 不是 sum.

        在 GIL Python 里, 真正并行要靠 asyncio 协程 (前提是 llm_call 是 async). 教学版用
        asyncio.gather, 假设 llm_call 是 IO-bound 协程友好.
        """
        if tools_allowed_per is None:
            tools_allowed_per = [None] * len(requests)
        if len(tools_allowed_per) != len(requests):
            raise ValueError(
                "tools_allowed_per must contain one entry for every request"
            )
        tasks = [
            self.delegate(agent_type, task, tools_allowed=allowed)
            for (agent_type, task), allowed in zip(
                requests, tools_allowed_per, strict=True
            )
        ]
        return await asyncio.gather(*tasks)


__all__ = ["Orchestrator", "SubAgent", "SubAgentResult"]
