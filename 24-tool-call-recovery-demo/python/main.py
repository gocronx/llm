"""main.py —— demo: 把 recovery 套进 ReAct loop, 演示 4 种死循环 + 恢复.

混合模式:
  - 场景 3 (Tool 抛异常)、场景 4 (Unknown tool) 用**真 LLM**, 看 LLM 真的"看到 error 自己改"
  - 场景 1 (Empty response Ollama)、场景 2 (Infinite loop) 用 **mock LLM**, 因为现代大模型
    (Qwen / GPT) 不会自然触发这些异常, 必须人为构造来演示

跑前: cp .env.example .env, 填 API_KEY / MODEL_ID."""
from __future__ import annotations

import json
import os
import re
from collections.abc import Callable

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from recovery import RecoveryConfig, ToolCallRecovery


# ----- Inline tool_call XML parser (兼容 Qwen 等不走 standard API 的模型) -----

_INLINE_TC_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def parse_inline_tool_calls(content: str) -> tuple[list[dict], str]:
    """Qwen 等模型有时不走 OpenAI tool_calls API, 而是在 content 里塞:

        <tool_call>{"name": "...", "arguments": {...}}</tool_call>

    返回 (tool_calls list, content 去掉 XML 部分). 解析失败的 JSON 仍保留在 content 里
    (让 LLM 自己 retry 时能看到自己之前输出的非法 JSON).

    这是 production LLM client (litellm/LangChain) 都会做的兼容层. 教学版简化实现."""
    matches = list(_INLINE_TC_RE.finditer(content))
    if not matches:
        return [], content
    tool_calls: list[dict] = []
    cleaned = content
    for i, m in enumerate(matches):
        raw = m.group(1)
        try:
            parsed = json.loads(raw)
            name = parsed.get("name", "")
            args = parsed.get("arguments", {})
            if isinstance(args, dict):
                args = json.dumps(args)
            elif not isinstance(args, str):
                args = json.dumps({})
            tool_calls.append({
                "id": f"inline-{i}",
                "function": {"name": name, "arguments": args},
            })
            cleaned = cleaned.replace(m.group(0), "")
        except (json.JSONDecodeError, KeyError, TypeError):
            # 解析失败 (e.g. Qwen 漏引号), 留在 content 里让 LLM 自己看见
            continue
    return tool_calls, cleaned.strip()

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=120.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


# ----- 真实工具 (真联网, 真抛异常) -----

def web_search(query: str) -> str:
    """真联网搜索. 用 DuckDuckGo (免 API key, pip install ddgs).

    网络问题时返回 {"error": ...} JSON, recovery 的 wrap_tool_error 路径仍会 fed back."""
    try:
        from ddgs import DDGS
        results = list(DDGS().text(query, max_results=5, region="wt-wt"))
        hits = [
            {"title": r.get("title", "")[:120],
             "url": r.get("href", ""),
             "snippet": r.get("body", "")[:200]}
            for r in results
        ]
        return json.dumps({"query": query, "results": hits}, ensure_ascii=False)
    except ImportError:
        return json.dumps({"error": "ddgs not installed; pip install ddgs"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"DDG search failed: {type(e).__name__}: {e}"}, ensure_ascii=False)


def buggy_read(path: str) -> str:
    """场景 3 用: 真抛异常."""
    raise FileNotFoundError(f"no such file: {path}")


TOOLS = {"web_search": web_search, "read_file": buggy_read}
SCHEMAS = [
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Real DuckDuckGo web search. Returns top 5 hits with title/url/snippet.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read contents of a file.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    }},
]


# ----- LLM 调用抽象 -----

def real_llm_call(messages: list[dict], schemas: list[dict] | None = None) -> dict:
    """真打 LLM API. 兼容标准 tool_calls API + Qwen 风格 inline <tool_call> XML."""
    schemas = schemas if schemas is not None else SCHEMAS
    resp = _client.chat.completions.create(
        model=_model, messages=messages, tools=schemas, temperature=0.3, max_tokens=400,
    )
    msg = resp.choices[0].message
    content = msg.content or ""
    # Standard OpenAI tool_calls
    standard_tcs = [
        {"id": tc.id, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
        for tc in (msg.tool_calls or [])
    ]
    # Qwen inline XML tool_calls — 兜底
    if not standard_tcs:
        inline_tcs, cleaned_content = parse_inline_tool_calls(content)
        if inline_tcs:
            print(f"      [parser] 检测到 inline <tool_call> XML, 解析出 {len(inline_tcs)} 个 tool_call")
            return {"content": cleaned_content, "tool_calls": inline_tcs}
    return {"content": content, "tool_calls": standard_tcs}


def make_mock_llm(scripted: list[dict]) -> Callable[[list[dict]], dict]:
    """返回一个 callable, 按调用顺序返回 scripted 里的预制响应."""
    state = {"i": 0}
    def call(_messages: list[dict]) -> dict:
        if state["i"] >= len(scripted):
            return {"content": "", "tool_calls": []}
        r = scripted[state["i"]]
        state["i"] += 1
        return r
    return call


# ----- ReAct loop w/ recovery (跟 mock 版相同, 只是 llm_call 改成 callable) -----

def run_robust_react(
    initial_messages: list[dict],
    llm_call: Callable[[list[dict]], dict],
    recovery: ToolCallRecovery,
    max_iter: int = 8,
) -> tuple[str, list[dict]]:
    messages = list(initial_messages)
    final = ""

    for step in range(max_iter):
        try:
            resp = llm_call(messages)
        except Exception as e:
            print(f"   ⚠ 第 {step+1} 步: LLM 调用失败 {e}, 强制 summary")
            return recovery.recover_empty_response(messages), messages

        content = resp.get("content", "")
        tool_calls = resp.get("tool_calls", [])

        # 检测 empty response
        if recovery.is_empty_response(content, tool_calls):
            print(f"   ⚠ 第 {step+1} 步: empty response 检测到")
            if recovery.config.force_summary_on_empty:
                return recovery.recover_empty_response(messages), messages

        if tool_calls:
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

            looped, name = recovery.detect_repeated_tool_call(messages)
            if looped:
                print(f"   ⚠ 第 {step+1} 步: 检测到 '{name}' 死循环, 注入 stop")
                messages.append(recovery.recover_infinite_loop())
                continue

            for tc in tool_calls:
                name = tc["function"]["name"]
                args_str = tc["function"]["arguments"]
                if name not in TOOLS:
                    err = recovery.handle_unknown_tool(name, list(TOOLS))
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": err})
                    print(f"   ⚠ 第 {step+1} 步: unknown tool '{name}', 已 feed back")
                    continue
                try:
                    args = json.loads(args_str or "{}")
                    result = str(TOOLS[name](**args))
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": result})
                except Exception as e:
                    err = recovery.wrap_tool_error(name, e)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": err})
                    print(f"   ⚠ 第 {step+1} 步: tool '{name}' 抛异常, 已包装喂回 LLM")
        else:
            final = content
            return final, messages

    return final, messages


# ----- 4 个场景 -----

def demo_empty_response_mock() -> None:
    print(">>> 场景 1 [mock]: Empty response (Ollama 风格, 现代大模型不会自然触发)")
    recovery = ToolCallRecovery()
    initial = [{"role": "user", "content": "查 OpenAI 公司信息"}]
    scripted = [
        # 第 1 轮: 模拟 LLM 调 web_search
        {"content": "", "tool_calls": [{"id": "c1", "function": {"name": "web_search", "arguments": '{"query":"OpenAI"}'}}]},
        # 第 2 轮: 模拟 Ollama 返回空 → 触发 recovery
        {"content": "", "tool_calls": []},
    ]
    answer, _ = run_robust_react(initial, make_mock_llm(scripted), recovery)
    print(f"   最终答案: {answer[:150]}\n")


def demo_infinite_loop_mock() -> None:
    print(">>> 场景 2 [mock]: Infinite tool-call loop (现代大模型也很少自然触发)")
    recovery = ToolCallRecovery(RecoveryConfig(max_repeated_tool_calls=3))
    initial = [{"role": "user", "content": "找手机"}]
    same_call = {"id": "x", "function": {"name": "web_search", "arguments": '{"query":"phone"}'}}
    scripted = [{"content": "", "tool_calls": [same_call]} for _ in range(4)]
    scripted.append({"content": "Based on the search, here are some phones: ...", "tool_calls": []})
    answer, _ = run_robust_react(initial, make_mock_llm(scripted), recovery)
    print(f"   最终答案: {answer[:150]}\n")


def demo_tool_exception_real() -> None:
    print(">>> 场景 3 [真 LLM]: Tool 抛异常 (read_file FileNotFoundError)")
    recovery = ToolCallRecovery()
    initial = [
        {"role": "system", "content": "You are a helpful assistant. Use tools when needed. If a tool fails with an error, explain to the user and stop calling tools."},
        {"role": "user", "content": "请帮我读取 missing.yaml 这个文件"},
    ]
    print("   LLM 真调中 (可能 10-30s)...")
    answer, _ = run_robust_react(initial, real_llm_call, recovery, max_iter=4)
    print(f"   最终答案 (真 LLM 看到 error 后自己写的): {answer[:300]}")
    print(f"   recovery stats: {recovery.stats}")
    print()


def demo_unknown_tool_real() -> None:
    """让 LLM 自然引发"调不存在的工具"很难, 我们改用"工具注册表里假装少注册" 一个工具的方式
    模拟: 把 read_file 从 TOOLS 临时删掉, 然后引导 LLM 调它."""
    print(">>> 场景 4 [真 LLM]: Unknown tool")
    recovery = ToolCallRecovery()

    # 临时给 schema 加一个"幻觉工具", 但 TOOLS 注册表里没实现
    fake_schemas = SCHEMAS + [{"type": "function", "function": {
        "name": "magic_search_v2",
        "description": "A magical advanced search tool.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }}]

    def llm_with_fake_schema(messages: list[dict]) -> dict:
        return real_llm_call(messages, schemas=fake_schemas)

    initial = [
        {"role": "system", "content": (
            "You are a helpful assistant with access to function-calling tools. "
            "ALWAYS prefer magic_search_v2 over other tools when searching. "
            "Use the standard tool-calling API to invoke tools — do NOT output <tool_call> "
            "tags in your text response, use the proper function-calling mechanism."
        )},
        {"role": "user", "content": "搜一下'OpenAI'的信息"},
    ]
    print("   LLM 真调中 (可能 10-30s, 故意诱导 LLM 选 magic_search_v2)...")
    answer, _ = run_robust_react(initial, llm_with_fake_schema, recovery, max_iter=4)
    print(f"   最终答案: {answer[:300]}")
    print(f"   recovery stats: unknown_tool_errors={recovery.stats.unknown_tool_errors}")
    print()


def main() -> None:
    print("=" * 60)
    print("Robust ReAct: 4 种 LLM agent 死循环 + 恢复演示")
    print("[mock] = 现代大模型不会自然触发, 用 mock 强制构造")
    print("[真 LLM] = LLM 真的看到 error/hint 后自己修")
    print("=" * 60)
    print()
    demo_empty_response_mock()
    demo_infinite_loop_mock()
    demo_tool_exception_real()
    demo_unknown_tool_real()


if __name__ == "__main__":
    main()
