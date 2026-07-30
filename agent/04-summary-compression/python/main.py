"""main.py —— demo: 真调 LLM 把一段长 history 压成结构化 summary."""
from __future__ import annotations

import os
from dataclasses import asdict

import httpx
from compressor import CompactConfig, LLMCompactor
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=120.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


def llm_call(prompt: str, max_tokens: int) -> str:
    """LLM summarization 调用. 单 turn prompt, 无 tool, 低温."""
    resp = _client.chat.completions.create(
        model=_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""


def make_realistic_history() -> list[dict]:
    """造一段"refactor auth module"的长对话, ~12 轮."""
    msgs = [{"role": "system", "content": "You are a helpful coding assistant."}]
    msgs.append({"role": "user", "content": "请帮我把 auth 模块从 session 改成 JWT"})

    fake_turns = [
        ("我先看下当前 auth 模块的代码结构", "read_file", '{"path":"auth/middleware.py"}',
         "auth/middleware.py 内容: 200 行的 session-based 中间件, 用 Redis 存 session id"),
        ("我看到 session 在 Redis 里, 现在需要看 user model", "read_file", '{"path":"models/user.py"}',
         "models/user.py: User class, password_hash 字段, 没有 jwt-related 字段"),
        ("user model 没问题, 我需要加 JWT 工具函数", "write_file", '{"path":"auth/jwt.py","content":"..."}',
         "auth/jwt.py 已写入, 64 行, 含 sign_token 和 verify_token"),
        ("接下来替换 middleware", "write_file", '{"path":"auth/middleware.py","content":"..."}',
         "auth/middleware.py 已更新, 改成调 verify_token"),
        ("跑测试看是否过", "run_tests", '{"path":"tests/auth"}',
         "12 个测试, 3 个失败: test_token_expiry, test_invalid_token, test_refresh"),
        ("test_token_expiry 失败因为 exp 字段没设, 修复", "write_file", '{"path":"auth/jwt.py"}',
         "auth/jwt.py 更新, 加 exp = now + 24h"),
        ("再跑一次测试", "run_tests", '{"path":"tests/auth"}',
         "12/12 passed ✓"),
        ("最后要更新文档", "write_file", '{"path":"docs/auth.md"}',
         "docs/auth.md 已更新"),
    ]
    for i, (thought, tool_name, tool_args, tool_result) in enumerate(fake_turns):
        msgs.append({
            "role": "assistant",
            "content": thought,
            "tool_calls": [{"id": f"c{i}", "function": {"name": tool_name, "arguments": tool_args}}],
        })
        msgs.append({
            "role": "tool", "tool_call_id": f"c{i}", "name": tool_name,
            "content": tool_result + "\n\n" + ("详细 trace: " + "x" * 300),  # 撑长一点
        })

    msgs.append({"role": "user", "content": "看起来 done 了, 帮我总结一下做了什么"})
    return msgs


def main() -> None:
    messages = make_realistic_history()
    compactor = LLMCompactor(
        llm_call,
        # threshold 故意调小到 500, 强制让这个 demo history 触发压缩 (实际生产用 4000+)
        CompactConfig(threshold_tokens=500, keep_recent_turns=2, target_summary_tokens=400),
    )

    print(f">>> 原始 history: {len(messages)} 条消息")
    print(f"   估算 tokens: {compactor._estimate(messages)}")
    print(f"   should_compact: {compactor.should_compact(messages)}")
    print()

    if not compactor.should_compact(messages):
        print("不到阈值, 不压缩.")
        return

    print(">>> 调用 LLM 压缩中...")
    result = compactor.compact(messages)

    if not result.compacted:
        print(f"压缩失败: {result.failure_reason}")
        return

    print(f">>> 压缩成功. 总结了 {result.n_turns_summarized} 条 middle messages")
    print(f"   新 messages 数: {len(result.new_messages)}")
    print(f"   新估算 tokens: {compactor._estimate(result.new_messages)}")
    print()
    print(">>> LLM 生成的 summary:")
    print("-" * 60)
    print(result.summary_text)
    print("-" * 60)
    print()
    print(">>> 新 messages 结构:")
    for i, m in enumerate(result.new_messages):
        role = m.get("role")
        content = (m.get("content") or "")[:80]
        marker = "📋" if "[Conversation summary" in (m.get("content") or "") else " "
        print(f"   [{i}] {marker} {role:<10} {content}")


if __name__ == "__main__":
    main()
