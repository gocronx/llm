"""governance.py —— ReAct 长对话的 5 步 context 治理组合拳。

09 教了 ReAct 长啥样。但跑 20+ 轮就会出三类崩：
  - **结构崩**：history 被截断后留下 assistant.tool_calls 没对应 tool 的孤儿 / tool 没对应 tool_calls
                的孤儿，OpenAI/Anthropic API 直接 400
  - **体积崩**：单个工具返回 50KB 文本，几轮就把 context 撑爆
  - **预算崩**：总 token 超 context window，LLM 直接拒绝

抽自 nanobot 的 5 个 staticmethod（runner.py:1103-1283），简化成 self-contained 教学版：

  drop_orphan_tool_results   tool 没爹 → 删
  backfill_missing_tool_results   tool_call 没儿 → 补占位
  microcompact               老 tool result → 一行摘要 (保留最近 N 个)
  apply_tool_result_budget   单 tool result 太大 → 截断
  snip_history               总 token 超预算 → 从最早开始砍

每个函数都是纯函数 (不改入参), 顺序无关 (但建议 drop→backfill→microcompact→budget→snip 这个顺序,
后一步可能让前一步重新出现孤儿, 所以 snip 后再 drop+backfill 一次, 见 govern()).
"""
from __future__ import annotations

from typing import Any

# ---- 调参常量（贴近 nanobot 默认值，留出微调空间）----
BACKFILL_CONTENT = "[Tool result unavailable — call was interrupted or lost]"
MICROCOMPACT_KEEP_RECENT = 10   # 最近 N 个可压缩 tool result 保留原文
MICROCOMPACT_MIN_CHARS = 500    # 小于这个长度的 tool result 不值得压
SNIP_SAFETY_BUFFER = 1024       # 预留给 max_tokens 输出 + tools schema 的缓冲

# 哪些工具的 result 老了可以丢只留摘要 —— 调用方按需扩展。
# 直觉：返回大块只读数据的 (文件/网页/搜索结果) 都可压；带副作用的 (写文件/下单) 别压。
COMPACTABLE_TOOLS: frozenset[str] = frozenset({
    "read_file", "exec", "grep", "web_search", "web_fetch", "list_dir",
    "search_products",  # 我们的 demo tool
})


def estimate_message_tokens(msg: dict[str, Any]) -> int:
    """Toy token 估计：chars / 4. 真生产用 tiktoken/Anthropic count_tokens.

    教学版不引 tiktoken 是为了 self-contained。chars/4 对英文/JSON 准, 中文偏低,
    实战要么换 tiktoken, 要么按 char/2.5 保守估。"""
    content = msg.get("content") or ""
    n = len(content) if isinstance(content, str) else len(str(content))
    for tc in msg.get("tool_calls") or []:
        if isinstance(tc, dict):
            fn = tc.get("function", {})
            n += len(fn.get("name", "")) + len(fn.get("arguments", ""))
    return max(1, n // 4)


def estimate_total_tokens(messages: list[dict[str, Any]]) -> int:
    return sum(estimate_message_tokens(m) for m in messages)


def drop_orphan_tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """删掉没有匹配 assistant.tool_calls 的 tool 消息。

    场景：history 中间被裁掉了 assistant 那条, 只剩 tool result 在后面。
    保留它会让 API 报"tool message must follow tool_calls"。"""
    declared: set[str] = set()
    updated: list[dict[str, Any]] | None = None
    for idx, msg in enumerate(messages):
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls") or []:
                if isinstance(tc, dict) and tc.get("id"):
                    declared.add(str(tc["id"]))
        if msg.get("role") == "tool":
            tid = msg.get("tool_call_id")
            if tid and str(tid) not in declared:
                # 第一次发现孤儿 → 把前面没问题的 message 复制到 updated, 继续过滤
                if updated is None:
                    updated = [dict(m) for m in messages[:idx]]
                continue
        if updated is not None:
            updated.append(dict(msg))
    return updated if updated is not None else messages


def backfill_missing_tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """assistant 说了 tool_call 但对应 tool result 丢失 → 补一条占位.

    场景：LLM 返回 tool_calls 后, 工具执行崩了, 历史里只有 assistant 没有 tool。
    下一轮 API 同样会 400, 必须补占位 (不补就只能整条 assistant 删, 但那样 LLM 失忆了)."""
    declared: list[tuple[int, str, str]] = []  # (assistant_idx, call_id, tool_name)
    fulfilled: set[str] = set()
    for idx, msg in enumerate(messages):
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls") or []:
                if isinstance(tc, dict) and tc.get("id"):
                    func = tc.get("function") or {}
                    declared.append((idx, str(tc["id"]), func.get("name", "")))
        elif msg.get("role") == "tool":
            tid = msg.get("tool_call_id")
            if tid:
                fulfilled.add(str(tid))

    missing = [(ai, cid, n) for ai, cid, n in declared if cid not in fulfilled]
    if not missing:
        return messages

    updated = list(messages)
    offset = 0
    for assistant_idx, call_id, name in missing:
        # 插到 assistant 后面的连续 tool 序列之后, 保持成对关系
        insert_at = assistant_idx + 1 + offset
        while insert_at < len(updated) and updated[insert_at].get("role") == "tool":
            insert_at += 1
        updated.insert(insert_at, {
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "content": BACKFILL_CONTENT,
        })
        offset += 1
    return updated


def microcompact(
    messages: list[dict[str, Any]],
    keep_recent: int = MICROCOMPACT_KEEP_RECENT,
    min_chars: int = MICROCOMPACT_MIN_CHARS,
    compactable_tools: frozenset[str] = COMPACTABLE_TOOLS,
) -> list[dict[str, Any]]:
    """把老的可压缩 tool result 替成一行摘要, 保留最近 N 个原文.

    跟 snip 的区别: snip 是"砍掉", microcompact 是"留壳去肉" —— LLM 还能看到这步发生过,
    但不再消耗大块 token. 适合 read_file / web_search 这类"只读外部数据"类工具."""
    compactable_indices = [
        i for i, m in enumerate(messages)
        if m.get("role") == "tool" and m.get("name") in compactable_tools
    ]
    if len(compactable_indices) <= keep_recent:
        return messages

    stale = compactable_indices[:-keep_recent] if keep_recent > 0 else compactable_indices
    updated: list[dict[str, Any]] | None = None
    for idx in stale:
        content = messages[idx].get("content")
        if not isinstance(content, str) or len(content) < min_chars:
            continue
        if updated is None:
            updated = [dict(m) for m in messages]
        name = messages[idx].get("name", "tool")
        updated[idx]["content"] = f"[{name} result omitted from context]"
    return updated if updated is not None else messages


def apply_tool_result_budget(
    messages: list[dict[str, Any]],
    max_tool_result_chars: int = 8000,
) -> list[dict[str, Any]]:
    """单个 tool result 超长 → 截断, 末尾标注省略."""
    updated: list[dict[str, Any]] | None = None
    for idx, msg in enumerate(messages):
        if msg.get("role") != "tool":
            continue
        content = msg.get("content")
        if not isinstance(content, str) or len(content) <= max_tool_result_chars:
            continue
        if updated is None:
            updated = [dict(m) for m in messages]
        head = max_tool_result_chars - 200
        omitted = len(content) - head
        updated[idx]["content"] = content[:head] + f"\n…[{omitted} chars truncated]"
    return updated if updated is not None else messages


def snip_history(
    messages: list[dict[str, Any]],
    context_window_tokens: int,
    reserve_for_output: int = 1024,
    safety_buffer: int = SNIP_SAFETY_BUFFER,
) -> list[dict[str, Any]]:
    """总 token 超预算 → 保 system + 第一条 user (任务定义) + 末尾若干 (assistant+tool*) 单元.

    关键设计:
    - **第一条 user 永远保**: 任务定义丢了 LLM 会偏题, 哪怕超预算也要保 (上层会再修)
    - **(assistant.tool_calls + 它的 tool result) 当 1 个 unit 整体保/丢**: 砍到一半会留孤儿,
      触发 govern 末尾的 drop_orphan 把"半截 unit"全清掉 → 最后还是孤的
    - 反向遍历, 从末尾 unit 开始保, 直到下一个 unit 会超预算"""
    if not messages or not context_window_tokens:
        return messages

    budget = context_window_tokens - reserve_for_output - safety_buffer
    if budget <= 0 or estimate_total_tokens(messages) <= budget:
        return messages

    system_msgs = [dict(m) for m in messages if m.get("role") == "system"]
    non_system = [dict(m) for m in messages if m.get("role") != "system"]
    if not non_system:
        return messages

    # 找第一条 user (任务定义, 必保)
    first_user_idx = next(
        (i for i, m in enumerate(non_system) if m.get("role") == "user"), None
    )
    if first_user_idx is None:
        return messages   # 退化: 没有 user 不动, 让上层处理
    first_user = non_system[first_user_idx]

    system_tokens = sum(estimate_message_tokens(m) for m in system_msgs)
    first_user_tokens = estimate_message_tokens(first_user)
    remaining = max(128, budget - system_tokens - first_user_tokens)

    # 反向收集 unit, 一个 unit = 1 条 user 或 1 条 (assistant + 它后面的 tool*)
    kept_tail: list[dict[str, Any]] = []
    kept_tokens = 0
    i = len(non_system) - 1
    while i > first_user_idx:
        # 从尾倒着走, 先吃掉连续的 tool, 再吃掉它前面的那条 assistant
        unit: list[dict[str, Any]] = []
        while i > first_user_idx and non_system[i].get("role") == "tool":
            unit.append(non_system[i])
            i -= 1
        if i > first_user_idx and non_system[i].get("role") == "assistant":
            unit.append(non_system[i])
            i -= 1
        elif not unit and i > first_user_idx:
            # 不带 tool 的 user/assistant 单条 (多轮对话场景), 单独成 unit
            unit.append(non_system[i])
            i -= 1
        if not unit:
            break
        unit.reverse()
        unit_tok = sum(estimate_message_tokens(m) for m in unit)
        if kept_tail and kept_tokens + unit_tok > remaining:
            break
        kept_tail = unit + kept_tail
        kept_tokens += unit_tok

    return system_msgs + [first_user] + kept_tail


def govern(
    messages: list[dict[str, Any]],
    context_window_tokens: int | None = None,
    reserve_for_output: int = 1024,
    max_tool_result_chars: int = 8000,
    microcompact_keep_recent: int = MICROCOMPACT_KEEP_RECENT,
) -> list[dict[str, Any]]:
    """5 步治理一气呵成. 顺序:

      1. drop_orphan_tool_results    清结构 (tool 没爹)
      2. backfill_missing_tool_results 补结构 (tool_call 没儿)
      3. microcompact                压老果
      4. apply_tool_result_budget    剪长果
      5. snip_history                兜总量
      6. drop_orphan + backfill 再来一次 (snip 可能产生新孤儿)
    """
    out = drop_orphan_tool_results(messages)
    out = backfill_missing_tool_results(out)
    out = microcompact(out, keep_recent=microcompact_keep_recent)
    out = apply_tool_result_budget(out, max_tool_result_chars=max_tool_result_chars)
    if context_window_tokens:
        out = snip_history(out, context_window_tokens, reserve_for_output=reserve_for_output)
    # snip 可能让 assistant.tool_calls 被半截砍掉, 再走一次结构修复
    out = drop_orphan_tool_results(out)
    out = backfill_missing_tool_results(out)
    return out
