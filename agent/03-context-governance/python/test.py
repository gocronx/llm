"""test.py —— 治理 5 函数 + govern() 组合的单元测试. 不调外网."""
from __future__ import annotations

from governance import (
    apply_tool_result_budget,
    backfill_missing_tool_results,
    drop_orphan_tool_results,
    estimate_total_tokens,
    govern,
    microcompact,
    snip_history,
)


def _asst(call_id: str, name: str = "search_products") -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": call_id, "function": {"name": name, "arguments": "{}"}}],
    }


def _tool(call_id: str, name: str = "search_products", content: str = "{}") -> dict:
    return {"role": "tool", "tool_call_id": call_id, "name": name, "content": content}


def test_drop_orphan() -> bool:
    """孤儿 tool (没匹配 assistant.tool_calls) 必须被删."""
    msgs = [
        {"role": "user", "content": "hi"},
        _tool("orphan-1", content="孤儿 result"),       # ← 这条要删
        _asst("c1"),
        _tool("c1", content="正常 result"),
    ]
    out = drop_orphan_tool_results(msgs)
    ok = len(out) == 3 and all(m.get("tool_call_id") != "orphan-1" for m in out)
    print(f"{'✓' if ok else '✗'} drop_orphan (kept {len(out)}/4)")
    return ok


def test_backfill_missing() -> bool:
    """assistant.tool_calls 没有匹配 tool → 补占位."""
    msgs = [
        {"role": "user", "content": "hi"},
        _asst("c1"),  # 没有 tool 跟随
        {"role": "user", "content": "继续"},
    ]
    out = backfill_missing_tool_results(msgs)
    ok = any(m.get("role") == "tool" and m.get("tool_call_id") == "c1"
             and "unavailable" in m.get("content", "") for m in out)
    print(f"{'✓' if ok else '✗'} backfill_missing (len {len(msgs)} -> {len(out)})")
    return ok


def test_microcompact() -> bool:
    """老的 search_products result (超 500 字符) 替成一行摘要, 最近 N 个保留原文."""
    big = "x" * 600  # 超 MIN_CHARS
    msgs = [_asst(f"c{i}") for i in range(5)]
    msgs += [_tool(f"c{i}", name="search_products", content=big) for i in range(5)]
    out = microcompact(msgs, keep_recent=2)
    omitted = sum(1 for m in out if m.get("role") == "tool" and "omitted" in m.get("content", ""))
    ok = omitted == 3  # 5 个 tool, 保留最近 2 个, 压缩 3 个
    print(f"{'✓' if ok else '✗'} microcompact ({omitted}/5 compacted)")
    return ok


def test_microcompact_skips_small() -> bool:
    """小于 MIN_CHARS 的 tool result 不该被压, 留原文."""
    small = "tiny"  # 远小于 500
    msgs = [_asst(f"c{i}") for i in range(15)]
    msgs += [_tool(f"c{i}", name="search_products", content=small) for i in range(15)]
    out = microcompact(msgs, keep_recent=10)
    omitted = sum(1 for m in out if "omitted" in (m.get("content") or ""))
    ok = omitted == 0
    print(f"{'✓' if ok else '✗'} microcompact skips small ({omitted}/15 should be 0)")
    return ok


def test_apply_budget() -> bool:
    """单条 tool result 超长 → 截断, 末尾标注省略字符数."""
    long = "y" * 20_000
    msgs = [_asst("c1"), _tool("c1", content=long)]
    out = apply_tool_result_budget(msgs, max_tool_result_chars=4000)
    truncated = out[1]["content"]
    ok = len(truncated) <= 4000 and "truncated" in truncated
    print(f"{'✓' if ok else '✗'} apply_budget ({len(long)} -> {len(truncated)})")
    return ok


def test_snip_history() -> bool:
    """总 token 超预算时, 保 system + 最近若干 user/assistant."""
    msgs = [{"role": "system", "content": "you are helpful"}]
    for i in range(30):
        msgs.append({"role": "user", "content": f"问题 {i}: " + "x" * 500})
        msgs.append({"role": "assistant", "content": f"答案 {i}: " + "y" * 500})

    before = estimate_total_tokens(msgs)
    out = snip_history(msgs, context_window_tokens=4000, reserve_for_output=512, safety_buffer=256)
    after = estimate_total_tokens(out)
    ok = (
        after < before
        and out[0]["role"] == "system"
        and any(m["role"] == "user" for m in out[:3])
        and len(out) < len(msgs)
    )
    print(f"{'✓' if ok else '✗'} snip_history ({len(msgs)}msgs/{before}tok -> {len(out)}msgs/{after}tok)")
    return ok


def test_govern_pipeline() -> bool:
    """组合: 制造一个含孤儿 + 大果实 + 超预算的 history, 跑完一遍 govern() 后所有问题应消失."""
    msgs = [{"role": "system", "content": "sys"}]
    msgs.append({"role": "user", "content": "go"})

    # 一堆"老"工具调用, 每个返回 6KB
    big = "z" * 6000
    for i in range(15):
        msgs.append(_asst(f"old-{i}"))
        msgs.append(_tool(f"old-{i}", name="search_products", content=big))

    # 一个孤儿 tool result
    msgs.append(_tool("ORPHAN", content="should-be-dropped"))

    # 一个没回的 tool_call
    msgs.append(_asst("unfulfilled"))

    out = govern(msgs, context_window_tokens=10_000, max_tool_result_chars=2000)

    has_orphan = any(m.get("tool_call_id") == "ORPHAN" for m in out)
    declared = {tc["id"] for m in out if m.get("role") == "assistant"
                for tc in (m.get("tool_calls") or [])}
    fulfilled = {m.get("tool_call_id") for m in out if m.get("role") == "tool"}
    pairs_ok = declared.issubset(fulfilled)
    oversize = any(m.get("role") == "tool" and len(m.get("content") or "") > 2000 for m in out)
    within_budget = estimate_total_tokens(out) <= (10_000 - 1024 - 1024)

    ok = (not has_orphan) and pairs_ok and (not oversize) and within_budget
    print(f"{'✓' if ok else '✗'} govern pipeline "
          f"(orphan={has_orphan}, pairs_ok={pairs_ok}, oversize={oversize}, in_budget={within_budget})")
    return ok


def main() -> None:
    tests = [
        test_drop_orphan,
        test_backfill_missing,
        test_microcompact,
        test_microcompact_skips_small,
        test_apply_budget,
        test_snip_history,
        test_govern_pipeline,
    ]
    passed = sum(t() for t in tests)
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
