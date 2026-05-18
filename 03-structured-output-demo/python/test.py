"""test.py —— 验证：
1) 简历 schema 的所有 required 字段都拿到了
2) 产品 schema 嵌套 price.amount 是 number 不是 string
3) 情感分类的 label 一定落在 enum 里"""
from __future__ import annotations

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


def test_resume_required() -> bool:
    r = extract(_client, _model, "提取简历信息。",
                "李四，30岁，前端工程师 ls@x.com，会 React、Vue", RESUME)
    ok = all(k in r for k in ["name", "age", "position", "email", "skills"]) \
        and isinstance(r["age"], int) and isinstance(r["skills"], list)
    print(f"{'✓' if ok else '✗'} resume: {r}")
    return ok


def test_product_nested_number() -> bool:
    r = extract(_client, _model, "提取产品信息。",
                "AirPods Pro 1899 元人民币，苹果，有货。", PRODUCT)
    ok = isinstance(r["price"]["amount"], (int, float)) and r["price"]["currency"] in ("CNY", "USD", "EUR")
    print(f"{'✓' if ok else '✗'} product: {r}")
    return ok


def test_sentiment_enum() -> bool:
    r = extract(_client, _model, "对文本做情感分类。",
                "服务很差，再也不来了。", SENTIMENT)
    ok = r["label"] in ("positive", "neutral", "negative")
    print(f"{'✓' if ok else '✗'} sentiment: {r}")
    return ok


def main() -> None:
    passed = sum([test_resume_required(), test_product_nested_number(), test_sentiment_enum()])
    print(f"\n{passed}/3 passed")


if __name__ == "__main__":
    main()
