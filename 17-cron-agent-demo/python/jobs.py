"""Scheduled job implementations."""

import os
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

import state

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")

SUMMARY_WINDOW_SECONDS = 120
SUMMARY_MIN_EVENTS = 5
SUMMARY_MAX_TOKENS = 150


def heartbeat() -> None:
    state.append_event({"job": "heartbeat", "status": "alive"})
    state.set_("last_heartbeat", datetime.now().isoformat(timespec="seconds"))
    print(f"  · heartbeat at {datetime.now():%H:%M:%S}")


def check_api() -> None:
    started = time.time()
    try:
        resp = requests.get(
            f"{API_BASE_URL}/models",
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=5,
        )
        event = {
            "job": "check_api",
            "status": "up" if resp.ok else "degraded",
            "http": resp.status_code,
            "latency_ms": int((time.time() - started) * 1000),
        }
    except requests.RequestException as e:
        event = {"job": "check_api", "status": "down", "error": str(e)}
    state.append_event(event)
    print(f"  · check_api: {event['status']:<10} {event.get('latency_ms', '-')}ms")


def summarize_recent() -> None:
    events = state.get_events_since(SUMMARY_WINDOW_SECONDS)
    if len(events) < SUMMARY_MIN_EVENTS:
        print(f"  · summarize_recent: only {len(events)} events, skip")
        return

    bullets = "\n".join(
        f"- {e['ts']}  {e.get('job', '?')}  {e.get('status', '')}"
        for e in events[-30:]
    )
    # 提示词故意压死"编模式"的倾向：只准报事实，不准从小样本算 interval / 推 trend。
    prompt = (
        "Summarize the events below in exactly ONE sentence. "
        "Only state event counts and overall status (up / down / mixed). "
        "Do NOT compute intervals between events. "
        "Do NOT claim patterns, trends, or 'consistent' anything — these are sampled "
        "events that may span multiple process restarts. "
        "Only flag a real anomaly if at least one event has status != 'alive' / 'up'.\n\n"
        + bullets
    )

    try:
        resp = requests.post(
            f"{API_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": SUMMARY_MAX_TOKENS,
            },
            timeout=60,
        )
        resp.raise_for_status()
        summary = resp.json()["choices"][0]["message"]["content"].strip()
    except requests.RequestException as e:
        summary = f"[LLM call failed: {e}]"

    state.set_("last_summary", {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event_count": len(events),
        "summary": summary,
    })
    print(f"  · summarize_recent ({len(events)} events): {summary[:120]}")
