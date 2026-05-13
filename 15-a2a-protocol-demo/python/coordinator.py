"""Coordinator agent: discovers specialists, decomposes user request, dispatches in parallel."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from protocol import AgentCard, TaskRequest, TaskResponse

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")
AGENT_TOKEN = os.getenv("AGENT_TOKEN")


def _auth_headers() -> dict[str, str]:
    """Bearer header for agent-to-agent calls. Empty when AGENT_TOKEN unset."""
    return {"Authorization": f"Bearer {AGENT_TOKEN}"} if AGENT_TOKEN else {}

# 硬编码的 agent 端点列表 —— 真实 A2A 会用 registry / DNS 发现
SPECIALIST_ENDPOINTS = [
    f"http://localhost:{os.getenv('TRANSLATOR_PORT', '8101')}",
    f"http://localhost:{os.getenv('REVIEWER_PORT', '8102')}",
    f"http://localhost:{os.getenv('SUMMARIZER_PORT', '8103')}",
]


def discover_agents() -> list[AgentCard]:
    """Pull /.well-known/agent.json from each known endpoint."""
    cards = []
    for url in SPECIALIST_ENDPOINTS:
        try:
            resp = requests.get(f"{url}/.well-known/agent.json", timeout=5)
            resp.raise_for_status()
            cards.append(AgentCard(**resp.json()))
        except Exception as e:
            print(f"  ! discover failed for {url}: {e}")
    return cards


# ---------- Decomposition: LLM decides which sub-tasks to dispatch ----------

DECOMPOSE_SYSTEM = (
    "You are a task router. Given a user request and a list of available agents "
    "(name + capabilities + what their tasks accept), output ONLY a JSON array of "
    "tasks to dispatch. Each task: "
    "{\"agent\": \"<name>\", \"task_type\": \"<capability>\", \"input\": {...}}. "
    "Return [] if none apply. Multiple tasks run in parallel — pick all that help. "
    "Do not explain. Start with [ end with ]."
)


def _agent_catalog(cards: list[AgentCard]) -> str:
    lines = []
    for c in cards:
        lines.append(f"- name: {c.name}")
        lines.append(f"  capabilities: {c.capabilities}")
        lines.append(f"  description: {c.description}")
    return "\n".join(lines)


def _input_schema_hint() -> str:
    """Minimal hint about what each task_type expects, so LLM fills 'input' right."""
    return (
        "Task input formats:\n"
        "- translate: {\"text\": <str>, \"target\": \"en\"|\"zh\"}\n"
        "- review-code: {\"code\": <str>, \"language\": <str>}\n"
        "- summarize: {\"text\": <str>, \"style\": \"paragraph\"|\"bullets\", \"max_sentences\": <int>}"
    )


def _extract_json_array(text: str) -> list | None:
    for end in range(len(text) - 1, -1, -1):
        if text[end] != "]":
            continue
        depth = 0
        for start in range(end, -1, -1):
            if text[start] == "]":
                depth += 1
            elif text[start] == "[":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:end + 1])
                    except json.JSONDecodeError:
                        break
        if depth != 0:
            continue
    return None


def decompose(user_request: str, cards: list[AgentCard]) -> list[dict]:
    user_msg = (
        f"Available agents:\n{_agent_catalog(cards)}\n\n"
        f"{_input_schema_hint()}\n\n"
        f"User request:\n{user_request}\n\n"
        f"JSON array of tasks:"
    )
    resp = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": DECOMPOSE_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.0,
            "max_tokens": 600,
        },
        timeout=120,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    tasks = _extract_json_array(text) or []
    return [t for t in tasks if isinstance(t, dict)]


# ---------- Dispatch: send each task to the right agent in parallel ----------

def dispatch(task: dict, cards: list[AgentCard]) -> TaskResponse:
    by_name = {c.name: c for c in cards}
    target = by_name.get(task.get("agent", ""))
    if target is None:
        return TaskResponse(
            task_id="-",
            state="failed",
            error=f"unknown agent {task.get('agent')!r}",
        )

    body = TaskRequest(
        task_id=f"task_{int(time.time() * 1000)}",
        task_type=task.get("task_type", ""),
        input=task.get("input", {}),
        requester="coordinator",
    ).model_dump()

    try:
        resp = requests.post(
            f"{target.endpoint}/tasks",
            json=body,
            headers=_auth_headers(),
            timeout=180,
        )
        resp.raise_for_status()
        return TaskResponse(**resp.json())
    except Exception as e:
        return TaskResponse(task_id=body["task_id"], state="failed", error=str(e))


def run_coordinator(user_request: str) -> dict:
    cards = discover_agents()
    if not cards:
        return {"error": "no agents discovered"}

    tasks = decompose(user_request, cards)
    if not tasks:
        return {"plan": [], "results": [], "note": "no specialist task needed"}

    # 并发执行
    results: list[tuple[dict, TaskResponse]] = []
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        futures = {pool.submit(dispatch, t, cards): t for t in tasks}
        for fut in as_completed(futures):
            results.append((futures[fut], fut.result()))

    return {
        "plan": tasks,
        "results": [
            {"task": t, "agent": t.get("agent"), "response": r.model_dump()}
            for t, r in results
        ],
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("request", help="natural-language request")
    args = parser.parse_args()

    out = run_coordinator(args.request)
    print(json.dumps(out, ensure_ascii=False, indent=2))
