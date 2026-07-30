"""recovery.py —— Agent loop 的几类死循环 / 错误恢复.

抽自 PraisonAI llm.py:1089 (`_generate_ollama_tool_summary`) + 实战中常见的 4 类问题.

## 几类"卡死"场景

### 1. Empty response loop (Ollama 类小模型常见)

LLM 调完工具, 收到 tool result, 但 **返回空 content + 空 tool_calls**. ReAct loop 一看 "没 tool_calls = 任务完成", 把空字符串当答案返回. 用户看到的是"啥都没说".

具体: Ollama / 一些小模型 (Qwen-7B 之类) 调完工具期望"用户主动 prompt 总结", 但 ReAct agent 没"用户", 死循环.

**修复**: 检测到 "tool_result 存在 + response 空", 强制基于 tool results 合成 summary 返回.

### 2. Infinite tool-call loop (反复调同一工具)

LLM 调 `search_products("手机")` → 收到结果 → 又调 `search_products("手机")` → 又调... 永远不进入回答阶段.

通常因为: tool 返回的内容不是 LLM 期望的格式; 或者 prompt 引导不够明确.

**修复**: 检测连续 N 次完全相同的 tool_call (name + args), 注入 system 消息 "不要重复, 已有结果请总结".

### 3. Tool error feed-back (传统重试不适用)

`exec("ls /nonexistent")` → 返回 `{"error": "no such file"}`.

传统重试: catch + retry. 但 LLM 重试同一个 prompt 还是 error.
**LLM 时代的修法**: error 当 tool result 返回, LLM 看到后会自己改 (改路径, 改命令). 不要 catch + raise.

### 4. Unknown tool call (LLM 幻觉一个不存在的工具)

LLM 调 `super_search_v2(...)`, 但 tools 里只注册了 `web_search`. 老 ReAct: KeyError 崩.

**修复**: 返回 `[error: unknown tool 'super_search_v2'. Available: web_search, read_file]`. LLM 看到列表会改用对的.

## 通用原则

> **错误信息要喂回给 LLM, 让它自己改; 不要抛异常停止 loop.**

这是 LLM-era error handling 跟传统的根本区别. 传统: catch → log → retry/raise. LLM-era: error → tool message → continue loop, LLM 看到 error 自我修复.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class RecoveryConfig:
    """各项检测的阈值."""

    max_repeated_tool_calls: int = 3  # 同 tool+args 连续超此次数 → 注入 stop 提示
    min_response_length: int = 10  # 短于此被认为"empty response"
    force_summary_on_empty: bool = True  # empty response 时是否强制合成 summary
    force_summary_after_n_tools: int = 8  # 连续调 N 个 tool 仍无 content → 强制总结


@dataclass
class RecoveryStats:
    empty_response_recoveries: int = 0
    infinite_loop_breaks: int = 0
    forced_summaries: int = 0
    unknown_tool_errors: int = 0
    tool_errors_fed_back: int = 0


class ToolCallRecovery:
    """检测 + 恢复. 设计成 stateless 的纯函数集合, 状态都在 stats / messages 里."""

    def __init__(self, config: RecoveryConfig | None = None):
        self.config = config or RecoveryConfig()
        self.stats = RecoveryStats()

    # ----- 检测 -----

    def is_empty_response(self, content: str | None, tool_calls: list | None) -> bool:
        """assistant 返回的 content 太短 + 没 tool_calls → empty.

        这种情况下 ReAct loop 会以为任务完成而退出, 但其实 LLM 没说什么."""
        if tool_calls:
            return False
        if content is None:
            return True
        return len(content.strip()) < self.config.min_response_length

    def detect_repeated_tool_call(
        self, messages: list[dict]
    ) -> tuple[bool, str | None]:
        """看末尾 N 次 assistant.tool_calls 是不是完全相同的 (name+args).

        返回 (是否检测到, 重复的 tool 名 / None)."""
        N = self.config.max_repeated_tool_calls
        recent_calls: list[tuple[str, str]] = []
        for m in reversed(messages):
            if m.get("role") == "assistant" and m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    fn = tc.get("function", {})
                    sig = (fn.get("name", ""), fn.get("arguments", ""))
                    recent_calls.append(sig)
                    if len(recent_calls) >= N:
                        break
            if len(recent_calls) >= N:
                break

        if len(recent_calls) < N:
            return False, None

        # 检查最近 N 个 tool_call 是否完全相同
        if all(c == recent_calls[0] for c in recent_calls):
            return True, recent_calls[0][0]
        return False, None

    def count_recent_tool_calls(self, messages: list[dict]) -> int:
        """末尾连续 tool 消息的数量 (一直到遇到非 tool 的 assistant content 为止)."""
        count = 0
        for m in reversed(messages):
            if m.get("role") == "tool":
                count += 1
            elif m.get("role") == "assistant":
                if (
                    m.get("content")
                    and len(m["content"].strip()) > self.config.min_response_length
                ):
                    break  # 有过实质 content 中断, 重置计数
                # assistant.tool_calls 且无 content, 继续
                continue
            else:
                break
        return count

    # ----- 恢复 -----

    def synthesize_summary_from_tools(self, messages: list[dict]) -> str:
        """从 messages 末尾的 tool results 合成一个文本回答.

        策略: 取最近 K 个 tool message 的 content, 拼成"工具调用历史 → 我整理给你"格式.

        生产中这里**应该再调一次 LLM 让它总结**, 教学版用规则拼接保 self-contained."""
        tool_results: list[tuple[str, str]] = []
        error_messages: list[str] = []
        for m in messages:
            if m.get("role") != "tool":
                continue
            content = m.get("content") or ""
            name = m.get("name", "tool")
            # 解析是否是 error
            try:
                parsed = json.loads(content) if isinstance(content, str) else content
                if isinstance(parsed, dict) and "error" in parsed:
                    error_messages.append(f"{name}: {parsed['error']}")
                    continue
            except (json.JSONDecodeError, TypeError):
                pass
            tool_results.append((name, content))

        if not tool_results and error_messages:
            return "I tried to complete the task but encountered errors: " + "; ".join(
                error_messages[-3:]
            )

        if not tool_results:
            return "I attempted some tool calls but didn't get usable results. Could you clarify the request?"

        # 拼成自然语言式回答 (最多 3 个结果)
        parts = []
        for name, result in tool_results[-3:]:
            short = result[:300] + ("..." if len(result) > 300 else "")
            parts.append(f"From {name}: {short}")

        return "Based on the tool results:\n" + "\n\n".join(parts)

    def recover_empty_response(self, messages: list[dict]) -> str:
        """LLM 返回 empty, 又没 tool_calls → 强制合成 summary."""
        self.stats.empty_response_recoveries += 1
        return self.synthesize_summary_from_tools(messages)

    def recover_infinite_loop(self) -> dict[str, Any]:
        """检测到 tool_call 死循环 → 注入一条 system 消息打断."""
        self.stats.infinite_loop_breaks += 1
        return {
            "role": "system",
            "content": (
                "STOP: You've called the same tool with the same arguments multiple times. "
                "The tool has already given you its result. Now synthesize a final answer "
                "for the user based on the existing tool results. Do not call more tools."
            ),
        }

    def wrap_tool_error(self, tool_name: str, error: Exception) -> str:
        """工具抛异常时, 不 raise, 包装成 LLM-readable error."""
        self.stats.tool_errors_fed_back += 1
        return json.dumps(
            {"error": f"{type(error).__name__}: {error}", "tool": tool_name},
            ensure_ascii=False,
        )

    def handle_unknown_tool(self, tool_name: str, available: list[str]) -> str:
        """LLM 调了不存在的工具, 提示它 available 列表."""
        self.stats.unknown_tool_errors += 1
        return json.dumps(
            {
                "error": f"unknown tool: '{tool_name}'",
                "available_tools": available[:20],
                "hint": "Use one of available_tools, or stop calling tools if you have enough info.",
            },
            ensure_ascii=False,
        )

    def should_force_summary(self, messages: list[dict]) -> bool:
        """末尾连续 N 个 tool message 都没 LLM 实质 content → 强制总结."""
        if not self.config.force_summary_on_empty:
            return False
        n_tools = self.count_recent_tool_calls(messages)
        return n_tools >= self.config.force_summary_after_n_tools
