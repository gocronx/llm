"""test.py —— 单元测试四种挡灾路径，全部用 fakesrv，确定性可重复。"""
from __future__ import annotations

import time

import httpx
from openai import OpenAI

from fakesrv import FakeServer
from resilient import Breaker, Endpoint, Resilient


def _client(base_url: str) -> OpenAI:
    return OpenAI(base_url=base_url, api_key="x",
                  http_client=httpx.Client(trust_env=False, timeout=2.0))


def test_retry_after_500() -> bool:
    """2 次 500 后第 3 次成功，应当返回成功内容。"""
    with FakeServer() as srv:
        srv.script("/chat/completions",
                   (500, None, "boom"), (500, None, "boom"), (200, None, "ok"))
        out = Resilient([Endpoint(_client(srv.base_url), "fake")]).chat("hi")
    ok = out == "ok"
    print(f"{'✓' if ok else '✗'} retry-on-500: {out!r}")
    return ok


def test_respect_retry_after() -> bool:
    """429 Retry-After=1，至少等 0.5 秒以上。"""
    with FakeServer() as srv:
        srv.script("/chat/completions", (429, 1.0, "rate"), (200, None, "ok"))
        t0 = time.perf_counter()
        Resilient([Endpoint(_client(srv.base_url), "fake")]).chat("hi")
        elapsed = time.perf_counter() - t0
    ok = elapsed >= 0.5
    print(f"{'✓' if ok else '✗'} respect Retry-After: waited {elapsed:.2f}s (≥0.5)")
    return ok


def test_fallback() -> bool:
    """primary 一直挂，secondary 顶上来。"""
    with FakeServer() as a, FakeServer() as b:
        a.script("/chat/completions", *[(500, None, "x")] * 6)
        b.script("/chat/completions", (200, None, "secondary"))
        out = Resilient([
            Endpoint(_client(a.base_url), "f", label="p"),
            Endpoint(_client(b.base_url), "f", label="s"),
        ]).chat("hi")
    ok = out == "secondary"
    print(f"{'✓' if ok else '✗'} fallback: {out!r}")
    return ok


def test_breaker_opens() -> bool:
    """连续失败 -> breaker open -> 后续调用应 skip primary 走 secondary。
    用 allow() 直接检查更确定（不依赖时间）。"""
    b = Breaker(threshold=3, cooldown_seconds=30)
    for _ in range(3):
        b.on_failure()
    ok = b.state == "open" and not b.allow()
    print(f"{'✓' if ok else '✗'} breaker opens after 3 fails")
    return ok


def main() -> None:
    passed = sum([
        test_retry_after_500(),
        test_respect_retry_after(),
        test_fallback(),
        test_breaker_opens(),
    ])
    print(f"\n{passed}/4 passed")


if __name__ == "__main__":
    main()
