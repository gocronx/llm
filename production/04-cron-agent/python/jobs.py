"""jobs.py —— 三个示例定时任务：heartbeat / check_api / summarize_recent。
整文件 cp 进项目即可（改 API 检查的 endpoint、加你自己的 job）。

每个 job 是一个无参函数。结果通过 state 持久化，跨进程重启可恢复。
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

import state

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.environ["API_BASE_URL"]
API_KEY = os.getenv("API_KEY", "not-needed")
MODEL_ID = os.environ["MODEL_ID"]

_http = httpx.Client(trust_env=False, timeout=60.0)
_client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY, http_client=_http)

SUMMARY_WINDOW_SECONDS = 120
SUMMARY_MIN_EVENTS = 5
SUMMARY_MAX_TOKENS = 150


def heartbeat() -> None:
    """每 30s 一次。证明 scheduler 还在跑，写一条事件 + 更新 last_heartbeat。"""
    state.append_event({"job": "heartbeat", "status": "alive"})
    state.set_("last_heartbeat", datetime.now().isoformat(timespec="seconds"))
    print(f"  · heartbeat at {datetime.now():%H:%M:%S}")


def check_api() -> None:
    """每 60s 探一次后端 /models 端点；记录 status / 状态码 / 延迟。"""
    started = time.time()
    try:
        resp = _http.get(f"{API_BASE_URL}/models",
                         headers={"Authorization": f"Bearer {API_KEY}"},
                         timeout=5.0)
        event = {
            "job": "check_api",
            "status": "up" if resp.is_success else "degraded",
            "http": resp.status_code,
            "latency_ms": int((time.time() - started) * 1000),
        }
    except httpx.HTTPError as e:
        event = {"job": "check_api", "status": "down", "error": str(e)}
    state.append_event(event)
    print(f"  · check_api: {event['status']:<10} {event.get('latency_ms', '-')}ms")


def summarize_recent() -> None:
    """每 120s 让 LLM 用一句话总结最近事件。事件不够 5 条就跳过。
    prompt 故意压死"编故事"倾向 —— 模型最爱从小样本里推出 interval / trend。"""
    events = state.get_events_since(SUMMARY_WINDOW_SECONDS)
    if len(events) < SUMMARY_MIN_EVENTS:
        print(f"  · summarize_recent: only {len(events)} events, skip")
        return

    bullets = "\n".join(
        f"- {e['ts']}  {e.get('job', '?')}  {e.get('status', '')}"
        for e in events[-30:]
    )
    prompt = (
        "Summarize the events below in exactly ONE sentence. "
        "Only state event counts and overall status (up / down / mixed). "
        "Do NOT compute intervals between events. "
        "Do NOT claim patterns or trends — these are sampled events that may span restarts. "
        "Only flag a real anomaly if at least one event has status != 'alive' / 'up'.\n\n"
        + bullets
    )

    try:
        resp = _client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=SUMMARY_MAX_TOKENS,
        )
        summary = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        summary = f"[LLM call failed: {e}]"

    state.set_("last_summary", {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event_count": len(events),
        "summary": summary,
    })
    print(f"  · summarize_recent ({len(events)} events): {summary[:120]}")
