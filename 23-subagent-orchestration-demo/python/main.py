"""main.py —— demo: 真调 LLM, 3 个 researcher subagent 并行调研三个主题.

跟 mock 版的区别:
  - llm_call 真打 OpenAI API
  - asyncio.gather + to_thread 在 thread pool 真并发, 不是顺序伪并发
  - 看真实 wall-clock 加速比

每个 subagent:
  1. LLM 看到任务: "Research X, return concise summary"
  2. LLM 决定调 web_search(query=X), 我们用 mock 给确定性结果 (避免真 web)
  3. LLM 综合 search result, 给最终 summary

工具 mock 是因为真 web search 在教学版不可行 (API key / 配额); 编排逻辑本身是真的."""
from __future__ import annotations

import asyncio
import json
import os
import time

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from orchestrator import Orchestrator, SubAgent

load_dotenv()


# ----- Mock 工具 (真 web 不可行, 但 LLM 决策真) -----

def web_search(query: str) -> str:
    """返回预编好的"搜索结果". LLM 拿到这个再综合."""
    knowledge = {
        "rope": [
            "RoPE = Rotary Position Embedding, from Su et al. 2021 (RoFormer).",
            "Rotates Q/K pairs by position-dependent angles (cos/sin matrix).",
            "Key property: <RoPE(q,m), RoPE(k,n)> depends only on (m-n) — true relative position encoding.",
            "Used in LLaMA, Mistral, Qwen, DeepSeek. YaRN extends to longer context via interp+extrap mix.",
        ],
        "rmsnorm": [
            "RMSNorm = Root Mean Square Layer Normalization, from Zhang & Sennrich 2019.",
            "Formula: y = x / sqrt(mean(x²) + eps) * gamma. Drops the mean-subtraction step of LayerNorm.",
            "Re-scaling matters, re-centering doesn't — paper shows accuracy unchanged but 10-50% faster.",
            "Modern LLMs (LLaMA family) use RMSNorm instead of LayerNorm.",
        ],
        "swiglu": [
            "SwiGLU = Swish-Gated Linear Unit, popularized by Shazeer 2020.",
            "Formula: silu(W_gate · x) * (W_up · x). 'Gate' learns which features to activate.",
            "Adds 1 extra projection (W_up) vs ReLU FFN, but quality gain is significant.",
            "Used in LLaMA, Mistral, PaLM. Replaces ReLU/GELU as the FFN activation.",
        ],
    }
    q = query.lower()
    for key, facts in knowledge.items():
        if key in q:
            return json.dumps({"results": facts}, ensure_ascii=False)
    return json.dumps({"results": [f"No matching facts for '{query}'"]}, ensure_ascii=False)


TOOLS = {"web_search": web_search}
SCHEMAS = {"web_search": {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search facts about a technical topic. Returns a list of relevant statements.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "the topic to search"}},
            "required": ["query"],
        },
    },
}}


# ----- 真 LLM client adapter -----

_http = httpx.Client(trust_env=False, timeout=120.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


def real_llm_call(messages: list[dict], schemas: list[dict]) -> dict:
    """SubAgent 期望的 (messages, schemas) → {content, tool_calls} 适配器."""
    kwargs: dict = {
        "model": _model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 400,
    }
    if schemas:
        kwargs["tools"] = schemas
    resp = _client.chat.completions.create(**kwargs)
    msg = resp.choices[0].message
    return {
        "content": msg.content or "",
        "tool_calls": [
            {"id": tc.id, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in (msg.tool_calls or [])
        ],
    }


# ----- Demo -----

async def run_demo() -> None:
    orch = Orchestrator()
    for topic in ["RoPE", "RMSNorm", "SwiGLU"]:
        orch.register(
            f"researcher_{topic}",
            SubAgent(
                agent_type=f"researcher_{topic}",
                llm_call=real_llm_call,
                tool_registry=TOOLS, tool_schemas=SCHEMAS,
                system_prompt=(
                    f"You are a research subagent. Your task: research {topic} concisely. "
                    f"Use the web_search tool once to gather facts about {topic}, then synthesize "
                    f"a brief 2-3 sentence summary. Do not call web_search more than once."
                ),
                max_iterations=4,
            ),
        )

    print(">>> 任务: 3 个 researcher subagent 并行调研 RoPE / RMSNorm / SwiGLU")
    print(">>> LLM = 真 OpenAI 客户端 (本地 MLX), 工具 = mock web_search\n")

    # 串行 baseline
    print(">>> 先跑一遍串行 baseline ...")
    t0 = time.perf_counter()
    serial_results = []
    for topic in ["RoPE", "RMSNorm", "SwiGLU"]:
        r = await orch.delegate(f"researcher_{topic}", f"Research {topic} briefly.")
        serial_results.append(r)
    serial_elapsed = (time.perf_counter() - t0) * 1000
    print(f"   串行: {serial_elapsed:.0f} ms (3 个 subagent 一个接一个)\n")

    # 并行
    print(">>> 现在跑并行 (asyncio.gather + to_thread)...")
    t0 = time.perf_counter()
    parallel_results = await orch.delegate_parallel([
        ("researcher_RoPE", "Research RoPE briefly."),
        ("researcher_RMSNorm", "Research RMSNorm briefly."),
        ("researcher_SwiGLU", "Research SwiGLU briefly."),
    ])
    parallel_elapsed = (time.perf_counter() - t0) * 1000
    print(f"   并行: {parallel_elapsed:.0f} ms\n")

    speedup = serial_elapsed / parallel_elapsed if parallel_elapsed > 0 else float("inf")
    print(f">>> 加速比: {speedup:.2f}× (理论上限 3.0×, 实际受 LLM 服务并发承载力影响)\n")

    print(">>> 每个 subagent 的 summary:")
    for i, (r, topic) in enumerate(zip(parallel_results, ["RoPE", "RMSNorm", "SwiGLU"])):
        print(f"\n📋 Subagent #{i+1} ({topic}):")
        print(f"   status: {r.status}, iter: {r.n_iterations}, ms: {r.elapsed_ms:.0f}")
        print(f"   summary: {r.summary[:300]}{'...' if len(r.summary) > 300 else ''}")
        print(f"   artifacts (tool 调用次数): {dict((k, len(v)) for k, v in r.artifacts.items())}")


if __name__ == "__main__":
    asyncio.run(run_demo())
