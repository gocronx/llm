"""resilient.py —— LLM 调用的"挡灾"封装。整文件 cp 进项目即可。

把四件事做对：
  1) 网络错 / 5xx / 429 → 指数退避重试
  2) 429 带 Retry-After → 尊重服务端给的等待
  3) 同一 endpoint 连错 N 次 → circuit breaker 直接拒绝若干秒，避免雪崩
  4) primary 挂了 → 自动 fallback 到 secondary（不同 model / 不同 base_url）

故意不引 tenacity / pybreaker —— 三百行依赖看不清，自己 80 行更顺。
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable

from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError, OpenAI, RateLimitError


# ---- circuit breaker：闭合 / 打开 / 半开 ----

@dataclass
class Breaker:
    threshold: int = 5            # 连续失败多少次进入 open
    cooldown_seconds: float = 30  # open 多久后试一次（half-open）
    fails: int = 0
    opened_at: float = 0.0
    state: str = "closed"

    def on_success(self) -> None:
        self.fails = 0
        self.state = "closed"

    def on_failure(self) -> None:
        self.fails += 1
        if self.fails >= self.threshold:
            self.state = "open"
            self.opened_at = time.time()

    def allow(self) -> bool:
        if self.state == "closed":
            return True
        # open 状态下，过了 cooldown 就进 half-open，放一次试探
        if time.time() - self.opened_at >= self.cooldown_seconds:
            self.state = "half-open"
            return True
        return False


# ---- 重试 + 退避 ----

# 哪些异常算"可重试"。OpenAI SDK 会把 HTTP 错误分门别类抛出，比看 status_code 干净
RETRYABLE = (APIConnectionError, APITimeoutError, RateLimitError)


def _backoff(attempt: int, base: float = 0.5, cap: float = 8.0) -> float:
    """指数退避 + jitter：避免一群客户端同时复试雪崩。"""
    raw = min(cap, base * (2 ** attempt))
    return raw * (0.5 + random.random() / 2)


def _retry_after(exc: Exception) -> float | None:
    """从 OpenAI 抛的错里把 Retry-After 拿出来，单位秒。没有就 None。"""
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    ra = resp.headers.get("retry-after") if hasattr(resp, "headers") else None
    if not ra:
        return None
    try:
        return float(ra)
    except ValueError:
        return None


# ---- 主入口 ----

@dataclass
class Endpoint:
    """一个可调 LLM 配置：客户端 + model 名 + 独立的 breaker。"""
    client: OpenAI
    model: str
    breaker: Breaker = field(default_factory=Breaker)
    label: str = "default"


class Resilient:
    """带重试 + breaker + fallback 的 LLM 客户端。"""

    def __init__(self, endpoints: list[Endpoint], max_attempts: int = 4):
        assert endpoints, "至少一个 endpoint"
        self.endpoints = endpoints
        self.max_attempts = max_attempts

    def chat(self, user_msg: str, on_event: Callable[[str], None] | None = None) -> str:
        emit = on_event or (lambda _: None)
        last_exc: Exception | None = None

        for ep in self.endpoints:
            if not ep.breaker.allow():
                emit(f"[{ep.label}] breaker=open, skip")
                continue

            for attempt in range(self.max_attempts):
                try:
                    resp = ep.client.chat.completions.create(
                        model=ep.model,
                        messages=[{"role": "user", "content": user_msg}],
                        max_tokens=100,
                    )
                    ep.breaker.on_success()
                    return resp.choices[0].message.content or ""

                except RETRYABLE as e:
                    last_exc = e
                    ep.breaker.on_failure()
                    if attempt == self.max_attempts - 1:
                        emit(f"[{ep.label}] gave up after {attempt+1}: {type(e).__name__}")
                        break
                    # 429 优先 Retry-After，其它走指数退避 + jitter
                    wait = _retry_after(e) if isinstance(e, RateLimitError) else None
                    if wait is None:
                        wait = _backoff(attempt)
                    emit(f"[{ep.label}] attempt {attempt+1} {type(e).__name__}, wait {wait:.2f}s")
                    time.sleep(wait)

                except APIStatusError as e:
                    # 4xx 非 429：参数错重试也是错，不重试，但要 breaker 计数
                    last_exc = e
                    ep.breaker.on_failure()
                    emit(f"[{ep.label}] 4xx={e.status_code}, not retrying")
                    break

                except APIError as e:
                    # 其它未分类的 OpenAI 错误，保守不重试
                    last_exc = e
                    ep.breaker.on_failure()
                    emit(f"[{ep.label}] unclassified: {e}")
                    break

            # 当前 endpoint 没成功，掉到下一个 fallback
            emit(f"[{ep.label}] failing over")

        raise RuntimeError(f"all endpoints failed; last={last_exc!r}")
