"""Common scaffolding for A2A agents: FastAPI app factory + LLM client."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Callable

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException

# 让子进程从 launcher 启动时仍能找到 .env
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")
AGENT_TOKEN = os.getenv("AGENT_TOKEN")  # None → 不要求 auth

# 把 python/ 加到 sys.path 让相对导入工作
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from protocol import AgentCard, AuthSpec, TaskRequest, TaskResponse  # noqa: E402


def call_llm(system: str, user: str, max_tokens: int = 600) -> str:
    resp = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _verify_bearer(authorization: str | None = Header(default=None)):
    """FastAPI dependency. Raises 401/403 unless a valid bearer token is presented.

    If AGENT_TOKEN env is not set, auth is disabled (returns immediately).
    """
    if AGENT_TOKEN is None:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != AGENT_TOKEN:
        raise HTTPException(status_code=403, detail="invalid token")


def make_app(
    card: AgentCard,
    handlers: dict[str, Callable[[dict], dict]],
) -> FastAPI:
    """Build a FastAPI app that exposes the A2A endpoints for one agent.

    handlers: maps task_type → function(input_dict) → output_dict.
    Auth: /tasks requires Bearer token if AGENT_TOKEN env is set.
    /.well-known/agent.json and /health are always public (per A2A convention).
    """
    # 在 card 上声明 auth 要求
    if AGENT_TOKEN is not None and card.auth is None:
        card.auth = AuthSpec(scheme="bearer")

    app = FastAPI(title=card.name)

    @app.get("/.well-known/agent.json", response_model=AgentCard)
    def get_card() -> AgentCard:
        return card

    @app.post(
        "/tasks",
        response_model=TaskResponse,
        dependencies=[Depends(_verify_bearer)],
    )
    def handle_task(req: TaskRequest) -> TaskResponse:
        if req.task_type not in handlers:
            return TaskResponse(
                task_id=req.task_id,
                state="failed",
                error=f"unsupported task_type {req.task_type!r}; "
                      f"supported: {list(handlers)}",
            )
        try:
            output = handlers[req.task_type](req.input)
            return TaskResponse(task_id=req.task_id, state="completed", output=output)
        except Exception as e:
            return TaskResponse(task_id=req.task_id, state="failed", error=str(e))

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "name": card.name}

    return app


def serve(app: FastAPI, port: int, name: str) -> None:
    """Start uvicorn with a startup banner and env-controlled log level.

    Env: AGENT_LOG_LEVEL (default 'info'). Launcher sets 'warning' for subprocesses
    so the demo output isn't drowned in HTTP access logs.
    """
    import uvicorn

    log_level = os.getenv("AGENT_LOG_LEVEL", "info")
    auth_status = "bearer auth required" if AGENT_TOKEN else "no auth (open)"
    print(f"[{name}] listening on http://127.0.0.1:{port}  ({auth_status})")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level=log_level)


def new_task_id() -> str:
    return f"task_{uuid.uuid4().hex[:8]}"
