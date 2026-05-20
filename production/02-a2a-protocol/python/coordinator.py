"""coordinator.py —— A2A 调度方：发现 specialist → LLM 拆解 → 并行 dispatch。
整文件 cp 进项目即可。

它做三件事：
  1) discover_agents：拉 /.well-known/agent.json 拿到每个 specialist 的能力描述
  2) decompose：让 LLM 把用户请求拆成可派发的子任务（指定 agent + task_type + input）
  3) dispatch：并发把每个子任务 POST 到对应 agent 的 /tasks
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
from protocol import AgentCard, TaskRequest, TaskResponse
from util import extract_json_array

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.environ["API_BASE_URL"]
API_KEY = os.getenv("API_KEY", "not-needed")
MODEL_ID = os.environ["MODEL_ID"]
AGENT_TOKEN = os.getenv("AGENT_TOKEN")

# 真实 A2A 用 DNS / registry 发现；演示用硬编码端口
SPECIALIST_ENDPOINTS = [
    f"http://localhost:{os.getenv('TRANSLATOR_PORT', '8101')}",
    f"http://localhost:{os.getenv('REVIEWER_PORT', '8102')}",
    f"http://localhost:{os.getenv('SUMMARIZER_PORT', '8103')}",
]

_http = httpx.Client(trust_env=False, timeout=180.0)
_client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY, http_client=_http)


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {AGENT_TOKEN}"} if AGENT_TOKEN else {}


def discover_agents() -> list[AgentCard]:
    """从每个 endpoint 拉 well-known/agent.json。失败的 endpoint 跳过。"""
    cards: list[AgentCard] = []
    for url in SPECIALIST_ENDPOINTS:
        try:
            r = _http.get(f"{url}/.well-known/agent.json", timeout=5)
            r.raise_for_status()
            cards.append(AgentCard(**r.json()))
        except Exception as e:
            print(f"  ! discover failed for {url}: {e}")
    return cards


# ---- 让 LLM 拆任务 ----

_DECOMPOSE_SYSTEM = (
    "You are a task router. Given a user request and a list of available agents, "
    "output ONLY a JSON array of tasks: [{\"agent\":\"<name>\",\"task_type\":\"<cap>\",\"input\":{...}}]. "
    "Return [] if no specialist matches. Multiple tasks run in parallel — include all that help. "
    "Do not explain. Start with [ end with ]."
)


def _input_hint() -> str:
    """告诉 LLM 每个 task_type 期待的 input 字段。"""
    return (
        "Task input formats:\n"
        "- translate: {\"text\": <str>, \"target\": \"en\"|\"zh\"}\n"
        "- review-code: {\"code\": <str>, \"language\": <str>}\n"
        "- summarize: {\"text\": <str>, \"style\": \"paragraph\"|\"bullets\", \"max_sentences\": <int>}"
    )


def decompose(user_request: str, cards: list[AgentCard]) -> list[dict]:
    catalog = "\n".join(
        f"- name: {c.name}\n  capabilities: {c.capabilities}\n  description: {c.description}"
        for c in cards
    )
    resp = _client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": _DECOMPOSE_SYSTEM},
            {"role": "user",
             "content": f"Agents:\n{catalog}\n\n{_input_hint()}\n\nRequest:\n{user_request}\n\nJSON 数组："},
        ],
        temperature=0,
        max_tokens=600,
    )
    tasks = extract_json_array(resp.choices[0].message.content or "")
    return [t for t in tasks if isinstance(t, dict)]


# ---- 派发 ----

def dispatch(task: dict, cards: list[AgentCard]) -> TaskResponse:
    by_name = {c.name: c for c in cards}
    target = by_name.get(task.get("agent", ""))
    if target is None:
        return TaskResponse(task_id="-", state="failed",
                            error=f"unknown agent {task.get('agent')!r}")
    body = TaskRequest(
        task_id=f"task_{abs(hash(repr(task.get('input', {})) + task['task_type'])) % 100000}",
        task_type=task.get("task_type", ""),
        input=task.get("input", {}),
        requester="coordinator",
    ).model_dump()
    try:
        r = _http.post(f"{target.endpoint}/tasks", json=body, headers=_auth_headers(), timeout=180)
        r.raise_for_status()
        return TaskResponse(**r.json())
    except Exception as e:
        return TaskResponse(task_id=body["task_id"], state="failed", error=str(e))


def run_coordinator(user_request: str) -> dict:
    cards = discover_agents()
    if not cards:
        return {"error": "no agents discovered"}
    tasks = decompose(user_request, cards)
    if not tasks:
        return {"plan": [], "results": [], "note": "no specialist task needed"}

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
    import json
    p = argparse.ArgumentParser()
    p.add_argument("request")
    args = p.parse_args()
    print(json.dumps(run_coordinator(args.request), ensure_ascii=False, indent=2))
