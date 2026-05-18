"""main.py —— demo only：让 LLM 通过 MCP server 创建并读回一个 todo 文件。"""
from __future__ import annotations

import os
import sys

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from client import run_sync

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=60.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]

# 用同一个 Python 解释器拉起 server.py；workspace 放当前目录下
_workspace = os.path.abspath("test_workspace")
_server_cmd = sys.executable
_server_args = ["server.py", _workspace]


def main() -> None:
    print(">>> 让 LLM 通过 MCP 创建 todo.txt")
    print(run_sync(_server_cmd, _server_args, _client, _model,
                   "请在 todo.txt 里写三条 todo：1. 学习 MCP 2. 写 demo 3. 提 PR"))

    print("\n>>> 让 LLM 通过 MCP 列目录并读回 todo.txt")
    print(run_sync(_server_cmd, _server_args, _client, _model,
                   "先列出当前目录，然后读 todo.txt 的内容回给我。"))


if __name__ == "__main__":
    main()
