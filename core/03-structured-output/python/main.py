"""main.py —— demo only：三个场景。
1) 简历提取 2) 产品信息提取 3) 情感分类（enum 限定输出域）"""
from __future__ import annotations

import json
import os

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from client import extract
from schemas import PRODUCT, RESUME, SENTIMENT

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=60.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


def show(label: str, data: dict) -> None:
    print(f"\n>>> {label}")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    show("简历提取", extract(_client, _model,
        "提取简历信息。",
        "张三，28岁，Python 工程师，邮箱 zs@example.com，擅长 Django、FastAPI、PostgreSQL。",
        RESUME))

    show("产品信息提取", extract(_client, _model,
        "提取产品信息。",
        "iPhone 15 Pro 国行 9999 元，苹果出品，目前有货。",
        PRODUCT))

    show("情感分类（label 限定 positive/neutral/negative）", extract(_client, _model,
        "对文本做情感分类，给出 label / confidence(0-1) / 一句话 reason。",
        "这部电影完全是浪费时间，特效粗糙，剧情拖沓。",
        SENTIMENT))


if __name__ == "__main__":
    main()
