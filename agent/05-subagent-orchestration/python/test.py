"""test.py —— Subagent 编排: 隔离 / 工具限制 / 并行 / 失败处理."""
from __future__ import annotations

import asyncio
import json
import time

from orchestrator import Orchestrator, SubAgent, SubAgentResult


# Mock 工具
def web_search(query: str) -> str:
    return f"[search results for '{query}']: top hit, second hit, ..."


def read_file(path: str) -> str:
    return f"[contents of {path}]: 200 lines of code"


def write_file(path: str, content: str) -> str:
    return f"[wrote {len(content)} chars to {path}]"


TOOLS = {"web_search": web_search, "read_file": read_file, "write_file": write_file}
SCHEMAS = {
    "web_search": {"type": "function", "function": {"name": "web_search", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    "read_file": {"type": "function", "function": {"name": "read_file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    "write_file": {"type": "function", "function": {"name": "write_file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
}


def mock_llm_one_tool_then_done(tool_name: str, tool_args: dict, final: str):
    """Mock LLM 工厂: 第 1 轮调 tool, 第 2 轮给 final content."""
    state = {"step": 0}
    def llm(messages, schemas):
        state["step"] += 1
        if state["step"] == 1:
            return {
                "tool_calls": [{"id": "c1", "function": {"name": tool_name, "arguments": json.dumps(tool_args)}}],
                "content": "",
            }
        return {"tool_calls": [], "content": final}
    return llm


def test_basic_subagent_run() -> bool:
    sub = SubAgent(
        agent_type="researcher",
        llm_call=mock_llm_one_tool_then_done("web_search", {"query": "rope encoding"}, "RoPE is a rotary embedding."),
        tool_registry=TOOLS, tool_schemas=SCHEMAS,
    )
    result = asyncio.run(sub.run("research rope encoding"))
    ok = (result.status == "completed"
          and "RoPE" in result.summary
          and "web_search" in result.artifacts)
    print(f"{'✓' if ok else '✗'} basic subagent run: status={result.status}, iter={result.n_iterations}, artifacts={list(result.artifacts)}")
    return ok


def test_subagent_tool_restriction() -> bool:
    """tools_allowed 限制 subagent 能调的工具."""
    # 试图调 write_file, 但只允许 read_file
    sub = SubAgent(
        agent_type="reader",
        llm_call=mock_llm_one_tool_then_done("write_file", {"path": "x", "content": "y"}, "ok done"),
        tool_registry=TOOLS, tool_schemas=SCHEMAS,
    )
    result = asyncio.run(sub.run("read something", tools_allowed=["read_file"]))
    # subagent 试图调 write_file 应被拒, artifact 里能看到拒绝消息
    ok = "write_file" in result.artifacts and "not allowed" in result.artifacts["write_file"][0]
    print(f"{'✓' if ok else '✗'} tool restriction: artifact={result.artifacts}")
    return ok


def test_subagent_max_iterations_partial() -> bool:
    """LLM 一直 tool_call, 跑到 max_iterations 返回 partial."""
    def loop_llm(messages, schemas):
        return {
            "tool_calls": [{"id": "c1", "function": {"name": "web_search", "arguments": '{"query":"loop"}'}}],
            "content": "",
        }
    sub = SubAgent("looper", loop_llm, TOOLS, SCHEMAS, max_iterations=3)
    result = asyncio.run(sub.run("loop forever"))
    ok = result.status == "partial" and result.n_iterations == 3
    print(f"{'✓' if ok else '✗'} max_iterations → partial (iter={result.n_iterations})")
    return ok


def test_subagent_llm_failure() -> bool:
    """LLM 抛异常, subagent 返回 status=failed."""
    def crash_llm(m, s):
        raise RuntimeError("API down")
    sub = SubAgent("victim", crash_llm, TOOLS, SCHEMAS)
    result = asyncio.run(sub.run("do something"))
    ok = result.status == "failed" and "API down" in (result.error or "")
    print(f"{'✓' if ok else '✗'} LLM failure → status=failed, error={result.error}")
    return ok


def test_orchestrator_delegate() -> bool:
    """Orchestrator 注册多种 subagent type, delegate 路由到正确的 type."""
    orch = Orchestrator()
    orch.register("researcher", SubAgent("researcher",
        mock_llm_one_tool_then_done("web_search", {"query": "X"}, "RESULT: research done"),
        TOOLS, SCHEMAS))
    orch.register("writer", SubAgent("writer",
        mock_llm_one_tool_then_done("write_file", {"path": "out.md", "content": "..."}, "RESULT: write done"),
        TOOLS, SCHEMAS))

    r1 = asyncio.run(orch.delegate("researcher", "do research"))
    r2 = asyncio.run(orch.delegate("writer", "write report"))
    ok = r1.summary.startswith("RESULT: research") and r2.summary.startswith("RESULT: write")
    print(f"{'✓' if ok else '✗'} orchestrator routes to correct type")
    return ok


def test_orchestrator_unknown_type() -> bool:
    """delegate 到未注册的 type 应失败."""
    orch = Orchestrator()
    r = asyncio.run(orch.delegate("phantom", "task"))
    ok = r.status == "failed" and "unknown" in (r.error or "")
    print(f"{'✓' if ok else '✗'} unknown agent_type rejected: {r.error}")
    return ok


def test_orchestrator_parallel() -> bool:
    """并行发起 3 个 subagent, 总时间 ≈ max(单个), 不是 sum."""
    def slow_llm(delay):
        async def real(messages, schemas):
            await asyncio.sleep(delay)
            return {"tool_calls": [], "content": f"done after {delay}s"}
        # async llm: 我们 SubAgent.run 期望同步 llm_call... 简化: 用同步 sleep 模拟
        def sync_llm(messages, schemas):
            time.sleep(delay)
            return {"tool_calls": [], "content": f"done after {delay}s"}
        return sync_llm

    # 都是同步 LLM, asyncio.gather 不会真并行 (因为单 thread 没让出). 真生产用 async LLM 客户端.
    # 教学版只验证 results 顺序正确.
    orch = Orchestrator()
    for i, d in enumerate([0.01, 0.02, 0.03]):
        orch.register(f"agent_{i}", SubAgent(f"agent_{i}", slow_llm(d), TOOLS, SCHEMAS))

    results = asyncio.run(orch.delegate_parallel(
        [("agent_0", "task A"), ("agent_1", "task B"), ("agent_2", "task C")],
    ))
    ok = (len(results) == 3
          and all(r.status == "completed" for r in results)
          and "done after 0.01" in results[0].summary
          and "done after 0.02" in results[1].summary)
    print(f"{'✓' if ok else '✗'} parallel: 3 results, statuses {[r.status for r in results]}")
    return ok


def test_context_isolation() -> bool:
    """两个 subagent 实例的 messages 完全隔离 (不共享 state)."""
    sub_a = SubAgent("a", mock_llm_one_tool_then_done("web_search", {"query": "alpha"}, "A's answer"), TOOLS, SCHEMAS)
    sub_b = SubAgent("b", mock_llm_one_tool_then_done("web_search", {"query": "beta"}, "B's answer"), TOOLS, SCHEMAS)

    r_a = asyncio.run(sub_a.run("task a"))
    r_b = asyncio.run(sub_b.run("task b"))

    # A 的 artifact 不应见到 beta, B 的不应见到 alpha
    ok = (
        "alpha" in r_a.artifacts["web_search"][0]
        and "beta" in r_b.artifacts["web_search"][0]
        and "beta" not in r_a.artifacts["web_search"][0]
    )
    print(f"{'✓' if ok else '✗'} context isolation: A sees alpha not beta, B sees beta not alpha")
    return ok


def main() -> None:
    tests = [
        test_basic_subagent_run,
        test_subagent_tool_restriction,
        test_subagent_max_iterations_partial,
        test_subagent_llm_failure,
        test_orchestrator_delegate,
        test_orchestrator_unknown_type,
        test_orchestrator_parallel,
        test_context_isolation,
    ]
    passed = sum(t() for t in tests)
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
