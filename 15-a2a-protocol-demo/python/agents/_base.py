"""_base.py —— A2A agent 通用脚手架：FastAPI app factory + LLM 客户端 + Bearer auth。"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Callable

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from protocol import AgentCard, AuthSpec, TaskRequest, TaskResponse  # noqa: E402

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY", "not-needed")
MODEL_ID = os.getenv("MODEL_ID")
AGENT_TOKEN = os.getenv("AGENT_TOKEN")  # None 表示不验证

# 复用一个 OpenAI client；trust_env=False 避免本地代理坑（见 01 demo）
_http = httpx.Client(trust_env=False, timeout=120.0)
_client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY, http_client=_http)


def call_llm(system: str, user: str, max_tokens: int = 600) -> str:
    """统一的 LLM 入口，三个 specialist agent 都走这。"""
    resp = _client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


# ---- Bearer auth dependency ----

def _verify_bearer(authorization: str | None = Header(default=None)) -> None:
    """没设 AGENT_TOKEN 就跳过；设了就强制 Bearer header 匹配。"""
    if AGENT_TOKEN is None:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    if authorization.split(" ", 1)[1].strip() != AGENT_TOKEN:
        raise HTTPException(status_code=403, detail="invalid token")


def make_app(card: AgentCard, handlers: dict[str, Callable[[dict], dict]]) -> FastAPI:
    """造一个 specialist agent 的 FastAPI app。
    /.well-known/agent.json 是 A2A 约定的发现端点，永远公开；
    /tasks 走 Bearer auth（若启用）；/health 给 launcher 探活。"""
    if AGENT_TOKEN is not None and card.auth is None:
        card.auth = AuthSpec(scheme="bearer")

    app = FastAPI(title=card.name)

    @app.get("/.well-known/agent.json", response_model=AgentCard)
    def get_card() -> AgentCard:
        return card

    @app.post("/tasks", response_model=TaskResponse, dependencies=[Depends(_verify_bearer)])
    def handle_task(req: TaskRequest) -> TaskResponse:
        if req.task_type not in handlers:
            return TaskResponse(task_id=req.task_id, state="failed",
                                error=f"unsupported task_type {req.task_type!r}; supported: {list(handlers)}")
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
    """启动 uvicorn，log level 可被环境变量压低（launcher 给子进程压成 warning）。"""
    import uvicorn
    auth = "bearer auth" if AGENT_TOKEN else "open"
    print(f"[{name}] http://127.0.0.1:{port}  ({auth})")
    uvicorn.run(app, host="127.0.0.1", port=port,
                log_level=os.getenv("AGENT_LOG_LEVEL", "info"))


def new_task_id() -> str:
    return f"task_{uuid.uuid4().hex[:8]}"
