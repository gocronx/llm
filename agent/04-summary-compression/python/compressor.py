"""compressor.py —— LLM-driven 历史压缩.

抽自 hermes-agent/agent/context_compressor.py:793-891 (`_generate_summary`). 跟 H21 的
rule-based 治理互补 —— H21 是"砍/截/替占位符", H22 是"让 LLM 把老 history 总结成一段".

## 跟 H21 的区别

| | H21 microcompact | H22 LLM summary |
|--|-----------------|-----------------|
| 谁干活 | 规则代码 | LLM 自己 (额外 1 次 forward) |
| 操作单位 | 单条 tool result | 多轮 (user+assistant+tools) |
| 输出 | `[result omitted]` 占位字符串 | 结构化 markdown 摘要 |
| 何时用 | tool result 老了 | history 长到要压缩才能继续 |
| 信息损失 | 完全丢工具结果内容 | LLM 保留关键信息 |
| 成本 | 0 | 1 次 LLM forward (中等成本) |
| 适用 | 短期压缩 (5-10 轮) | 长会话 (50+ 轮) checkpoint |

实战中两者**叠加用**: 先 H21 微压缩单条, 仍超预算时 H22 整段总结.

## 压缩什么 / 保留什么

压缩 (扔进 LLM 总结):
  - 老的 (assistant, tool) 配对
  - 远古 user 输入

保留 (绕过压缩, 留原文):
  - system message (任务指令)
  - 最近 N 轮 (避免最近上下文丢失)
  - **第一条 user** (任务定义, 跟 H21 snip 同理)

替换后的 messages:
  [system, first_user, summary_message, ...recent_turns...]

## 结构化模板

不是让 LLM "随便总结", 而是给一个固定结构, 让总结可机器解析也可人读. 模板字段:

- **Active Task**: 用户最新指令 (复制原话)
- **Completed Actions**: 已做的事 (含工具名 + 结果)
- **In Progress**: 当前正在做的
- **Blocked**: 卡住的地方
- **Key Decisions**: 已做的技术决策 + WHY
- **Pending User Asks**: 用户问过但没答的
- **Remaining Work**: 还要做什么

(参考 hermes-agent 原版的 12 个 section. 教学版砍到 7 个核心字段.)

## 关键工程细节

1. **失败 fallback + cooldown**: LLM 总结可能失败 (rate limit, 截断). 失败后短时间内不重试,
   直接走 H21 的 rule-based fallback. 否则一个会话死循环重试.
2. **focus_topic**: Claude Code `/compact` 借鉴, 让总结偏向某话题 (e.g. "refactor auth").
   长会话里有时只关心一个子任务, 全总结浪费.
3. **summary 目标 token 数**: 太短 LLM 总结不全, 太长 = 没压缩. 一般取被压缩区的 5-15%.
4. **iterative update**: 已有 summary 时, 不重新总结, 在 summary 基础上 append 增量 (省 prompt token).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------- 结构化模板 ----------------

_SUMMARY_PREAMBLE = """You are a summarization agent creating a context checkpoint. \
Treat the conversation below as source material for a compact record. \
Produce ONLY the structured summary, no preamble or greeting. \
Write in the same language as the conversation. \
Replace any credentials/tokens/keys with [REDACTED]."""

_SUMMARY_TEMPLATE = """## Active Task
[Copy the user's most recent request verbatim. If multiple tasks, list only the ones NOT yet completed.]

## Goal
[What the user is trying to accomplish overall]

## Completed Actions
[Numbered list: N. ACTION target — outcome [tool: name]
Be specific: file paths, commands, line numbers, results.]

## In Progress
[Work currently underway when compaction fired]

## Blocked
[Errors / issues not yet resolved. Include exact error text.]

## Key Decisions
[Important decisions made and WHY]

## Pending User Asks
[Questions from user that have NOT been answered. "None" if all done.]

## Remaining Work
[What's left, framed as context not instructions]

Target ~{budget} tokens. Be CONCRETE — file paths, errors, values."""


# ---------------- Config + Result ----------------


@dataclass
class CompactConfig:
    """压缩配置. 调参指导见 README."""

    threshold_tokens: int = 4000  # 总 tokens 超此值触发压缩
    keep_recent_turns: int = 4  # 最近 N 轮保留原文 (跟 H21 keep_recent 同理)
    target_summary_tokens: int = 600  # summary 目标长度
    focus_topic: str | None = None  # 引导压缩偏向的子话题
    cooldown_seconds: float = 60.0  # LLM 总结失败后短期不重试


@dataclass
class CompactResult:
    compacted: bool = False
    n_turns_summarized: int = 0
    summary_text: str = ""
    new_messages: list[dict[str, Any]] = field(default_factory=list)
    failure_reason: str | None = None


# ---------------- 主类 ----------------


class LLMCompactor:
    """LLM-driven 历史压缩器.

    用法:
      llm = lambda prompt, max_tokens: openai.chat(...)
      compactor = LLMCompactor(llm, CompactConfig(threshold_tokens=4000))

      if compactor.should_compact(messages):
          result = compactor.compact(messages)
          if result.compacted:
              messages = result.new_messages
    """

    def __init__(
        self,
        llm_call: Callable[[str, int], str],
        config: CompactConfig | None = None,
        token_estimator: Callable[[list[dict]], int] | None = None,
    ):
        """llm_call(prompt, max_tokens) -> summary_text. 通常是对 OpenAI client 的薄包装."""
        self.llm_call = llm_call
        self.config = config or CompactConfig()
        self._cooldown_until = 0.0
        self._estimate = token_estimator or self._default_estimate

    @staticmethod
    def _default_estimate(messages: list[dict]) -> int:
        """chars/4 toy estimator. 跟 H21 一致. 生产换 tiktoken."""
        total = 0
        for m in messages:
            c = m.get("content") or ""
            total += len(c) if isinstance(c, str) else len(str(c))
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                total += len(fn.get("name", "")) + len(fn.get("arguments", ""))
        return total // 4

    def should_compact(self, messages: list[dict]) -> bool:
        """是否到达压缩阈值."""
        return self._estimate(messages) >= self.config.threshold_tokens

    # ----- 主流程 -----

    def compact(self, messages: list[dict]) -> CompactResult:
        """对 messages 做 LLM 压缩.

        切分逻辑:
          [system, first_user, ...middle (要压缩)..., ...recent_keep_n_turns (保留)..., user]

        若中间没东西可压缩 (e.g. 总轮数 <= keep_recent), 直接返回 compacted=False.
        若 LLM 总结失败, 进入 cooldown, 返回 compacted=False + failure_reason.
        """
        # cooldown 检查
        if time.monotonic() < self._cooldown_until:
            remaining = self._cooldown_until - time.monotonic()
            return CompactResult(failure_reason=f"in cooldown ({remaining:.0f}s)")

        # 切片
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        if len(non_system) <= self.config.keep_recent_turns + 1:
            return CompactResult(failure_reason="not enough turns to compress")

        # 第一条 user (任务定义) 保住
        first_user_idx = next(
            (i for i, m in enumerate(non_system) if m.get("role") == "user"), None
        )
        if first_user_idx is None:
            return CompactResult(failure_reason="no user message found")
        first_user = non_system[first_user_idx]

        # 最近 N "turn" 保留: 简化为最近 N*2 条 (每轮 user+assistant; 教学版别太复杂)
        recent_n = self.config.keep_recent_turns * 2
        recent = non_system[-recent_n:] if len(non_system) > recent_n else []

        # 要压缩的中间区域
        middle_start = first_user_idx + 1
        middle_end = len(non_system) - len(recent)
        middle = non_system[middle_start:middle_end]

        if not middle:
            return CompactResult(failure_reason="no middle range to compress")

        # 构造 LLM prompt
        serialized = self._serialize(middle)
        focus_line = (
            f"\nFocus topic (preserve info about this): {self.config.focus_topic}\n"
            if self.config.focus_topic
            else ""
        )
        prompt = (
            f"{_SUMMARY_PREAMBLE}\n{focus_line}\n"
            f"---\n{serialized}\n---\n\n"
            f"{_SUMMARY_TEMPLATE.format(budget=self.config.target_summary_tokens)}"
        )

        # 调 LLM
        try:
            summary = self.llm_call(prompt, self.config.target_summary_tokens)
        except Exception as e:
            self._cooldown_until = time.monotonic() + self.config.cooldown_seconds
            return CompactResult(failure_reason=f"LLM call failed: {e}")

        if not summary or not summary.strip():
            self._cooldown_until = time.monotonic() + self.config.cooldown_seconds
            return CompactResult(failure_reason="LLM returned empty summary")

        # 组装新 messages
        summary_msg = {
            "role": "system",
            "content": f"[Conversation summary, compacted {len(middle)} prior messages]\n\n{summary.strip()}",
        }
        new_messages = system_msgs + [first_user, summary_msg] + recent

        return CompactResult(
            compacted=True,
            n_turns_summarized=len(middle),
            summary_text=summary.strip(),
            new_messages=new_messages,
        )

    # ----- 辅助 -----

    @staticmethod
    def _serialize(messages: list[dict]) -> str:
        """把 messages list 序列化成 LLM 可读的纯文本. 简化: 只取关键字段."""
        lines = []
        for m in messages:
            role = m.get("role", "?")
            content = m.get("content") or ""
            if not isinstance(content, str):
                content = str(content)
            if m.get("role") == "assistant" and m.get("tool_calls"):
                tc_str = ", ".join(
                    f"{tc.get('function', {}).get('name', '?')}({tc.get('function', {}).get('arguments', '')[:80]}...)"
                    for tc in m["tool_calls"]
                )
                lines.append(f"[{role} called tools: {tc_str}]")
                if content:
                    lines.append(f"  thought: {content[:300]}")
            elif m.get("role") == "tool":
                name = m.get("name", "?")
                truncated = content[:400] + ("..." if len(content) > 400 else "")
                lines.append(f"[tool '{name}' returned]: {truncated}")
            else:
                lines.append(
                    f"[{role}]: {content[:500]}{'...' if len(content) > 500 else ''}"
                )
        return "\n".join(lines)
