"""main.py —— demo only：四个挡灾场景，全用 fakesrv，不用真 LLM。"""
from __future__ import annotations

import httpx
from openai import OpenAI

from fakesrv import FakeServer
from resilient import Breaker, Endpoint, Resilient


def _client(base_url: str) -> OpenAI:
    return OpenAI(base_url=base_url, api_key="not-needed",
                  http_client=httpx.Client(trust_env=False, timeout=2.0))


def scenario_basic_retry() -> None:
    print(">>> 场景 1：连吃 2 次 500，第 3 次成功")
    with FakeServer() as srv:
        srv.script("/chat/completions",
                   (500, None, "boom"), (500, None, "boom"), (200, None, "回答 A"))
        client = Resilient([Endpoint(_client(srv.base_url), "fake", label="primary")])
        out = client.chat("hi", on_event=print)
        print("=>", out, "\n")


def scenario_retry_after() -> None:
    print(">>> 场景 2：429 带 Retry-After=1，等 1s 重试")
    with FakeServer() as srv:
        srv.script("/chat/completions", (429, 1.0, "rate"), (200, None, "回答 B"))
        client = Resilient([Endpoint(_client(srv.base_url), "fake", label="primary")])
        out = client.chat("hi", on_event=print)
        print("=>", out, "\n")


def scenario_fallback() -> None:
    print(">>> 场景 3：primary 一直挂，自动 fallback 到 secondary")
    with FakeServer() as a, FakeServer() as b:
        a.script("/chat/completions",
                 *[(500, None, "down")] * 8)  # primary 全挂
        b.script("/chat/completions", (200, None, "secondary 顶上来"))
        client = Resilient([
            Endpoint(_client(a.base_url), "fake", label="primary"),
            Endpoint(_client(b.base_url), "fake", label="secondary"),
        ])
        out = client.chat("hi", on_event=print)
        print("=>", out, "\n")


def scenario_circuit_breaker() -> None:
    print(">>> 场景 4：连续失败 5 次进入 breaker open，下一次直接 skip")
    with FakeServer() as a, FakeServer() as b:
        a.script("/chat/completions", *[(500, None, "x")] * 20)
        b.script("/chat/completions", (200, None, "secondary"), (200, None, "secondary"))
        client = Resilient(
            [Endpoint(_client(a.base_url), "fake",
                      breaker=Breaker(threshold=5, cooldown_seconds=30), label="primary"),
             Endpoint(_client(b.base_url), "fake", label="secondary")],
            max_attempts=2,  # 让 primary 快速失败把 breaker 打开
        )
        # 调几次让 primary 累计失败 → breaker open
        for i in range(3):
            print(f"--- call #{i+1} ---")
            print("=>", client.chat("hi", on_event=print))


def main() -> None:
    scenario_basic_retry()
    scenario_retry_after()
    scenario_fallback()
    scenario_circuit_breaker()


if __name__ == "__main__":
    main()
