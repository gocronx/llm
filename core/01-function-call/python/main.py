"""main.py —— demo only：跑三个场景。"""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from client import run

load_dotenv()

# trust_env=False：绕过系统/环境代理。
# 坑：macOS 系统代理（HTTP_PROXY 或 SystemConfiguration）的 bypass 列表里通常有
# localhost，但 httpx 不读 bypass，会把 http://localhost:8000 也送进代理，导致
# RemoteProtocolError。本地模型场景下直接关掉环境代理最稳。
_http = httpx.Client(trust_env=False, timeout=60.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),  # 本地 MLX 不校验 key
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


def main() -> None:
    for q in [
        "北京今天天气怎么样？",
        "156 除以 12 等于多少？",
        "搜索价格在 500 元以上的产品",
    ]:
        print(f"\n>>> {q}")
        print(run(_client, _model, q))


if __name__ == "__main__":
    main()
