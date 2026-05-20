"""test.py —— batch 行为测试：load/append/resume + retry 路径，全部 mock 不调外网。"""
from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import batch


def t(label: str, cond: bool) -> bool:
    print(f"{'✓' if cond else '✗'} {label}")
    return cond


def test_load_jobs_skips_blank_lines() -> bool:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "in.jsonl"
        p.write_text('{"id":"a","prompt":"x"}\n\n{"id":"b","prompt":"y"}\n', encoding="utf-8")
        jobs = batch.load_jobs(p)
    return [j.id for j in jobs] == ["a", "b"]


def test_load_done_skips_failed() -> bool:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "out.jsonl"
        p.write_text(
            json.dumps({"id": "ok1", "error": None, "answer": "x"}) + "\n" +
            json.dumps({"id": "bad", "error": "boom", "answer": None}) + "\n",
            encoding="utf-8",
        )
        done = batch.load_done(p)
    return done == {"ok1"}  # bad 不算 done，下次重试


def test_run_one_retry_then_success() -> bool:
    """前两次 _single_call 抛 TransientError，第三次返回 ok。期待 attempts=3, error=None。"""
    calls = []

    def fake(prompt):
        calls.append(prompt)
        if len(calls) < 3:
            raise batch.TransientError("simulated 503")
        return "ok", 10

    with patch.object(batch, "_single_call", side_effect=fake):
        r = batch.run_one(batch.Job(id="x", prompt="hi"))
    return r.error is None and r.attempts == 3 and r.answer == "ok"


def test_run_one_gives_up_after_max_attempts() -> bool:
    """所有 attempt 都 TransientError，期待返回 error 不抛。"""
    with patch.object(batch, "_single_call",
                      side_effect=batch.TransientError("nope")):
        r = batch.run_one(batch.Job(id="x", prompt="hi"))
    return r.error is not None and r.attempts == batch.MAX_ATTEMPTS and r.answer is None


def test_run_one_does_not_retry_4xx() -> bool:
    """4xx 应该直接抛出（被 run_one 包成 error），不进 retry 循环。"""
    calls = []

    def fake(_prompt):
        calls.append(1)
        raise ValueError("400 bad request")  # 模拟非 transient

    with patch.object(batch, "_single_call", side_effect=fake):
        r = batch.run_one(batch.Job(id="x", prompt="hi"))
    return r.error is not None and len(calls) == 1


def test_append_result_idempotent_open() -> bool:
    """append_result 写一行后能被 load_done 读到。"""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "out.jsonl"
        r = batch.Result(id="z", prompt="p", answer="a", error=None,
                         elapsed_ms=1, attempts=1, tokens=5)
        batch.append_result(out, r)
        done = batch.load_done(out)
    return done == {"z"}


def main() -> None:
    passed = sum([
        t("load_jobs skips blank", test_load_jobs_skips_blank_lines()),
        t("load_done excludes failed", test_load_done_skips_failed()),
        t("run_one retries then succeeds", test_run_one_retry_then_success()),
        t("run_one gives up after MAX_ATTEMPTS", test_run_one_gives_up_after_max_attempts()),
        t("run_one no retry on non-transient", test_run_one_does_not_retry_4xx()),
        t("append_result round-trip", test_append_result_idempotent_open()),
    ])
    print(f"\n{passed}/6 passed")


if __name__ == "__main__":
    main()
