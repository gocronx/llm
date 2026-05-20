"""main.py —— demo only：四种技术在同一任务上的对比。
注意：技术之间不是互斥的，生产里经常 system + few_shot + structured 一起用。"""
from __future__ import annotations

import json
import os

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from techniques import baseline, chain_of_thought, few_shot, structured, system_prompt

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=60.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


def s1_system_prompt() -> None:
    print("\n=== 1. System Prompt：约束角色 ===")
    q = "解释一下什么是 HTTP"
    print(f"baseline:   {baseline(_client, _model, q)[:120]}")
    print(f"system:     {system_prompt(_client, _model, q, '你只用一句话回答，不超过 30 字。')[:120]}")


def s2_few_shot() -> None:
    print("\n=== 2. Few-shot：用示例锁输出格式 ===")
    q = "把这句翻译成英文：人工智能很有趣"
    print(f"baseline:   {baseline(_client, _model, q)}")
    print(f"few-shot:   {few_shot(_client, _model, q)}")


def s3_chain_of_thought() -> None:
    print("\n=== 3. Chain of Thought：推理题准确率 ===")
    q = ("小明有 23 个苹果。他给了小红 5 个，又买了 12 个，"
         "然后吃掉了一半。他现在有多少个苹果？")
    print(f"baseline:   {baseline(_client, _model, q)[:200]}")
    print(f"CoT:        {chain_of_thought(_client, _model, q)[:400]}")


def s4_structured() -> None:
    print("\n=== 4. Structured Output：强制 JSON ===")
    schema = {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
            "temp_c": {"type": "number"},
            "condition": {"type": "string"},
        },
        "required": ["city", "temp_c", "condition"],
        "additionalProperties": False,
    }
    q = "假设北京今天 25 度晴天，把这条天气信息结构化输出。"
    print(f"baseline:   {baseline(_client, _model, q)[:120]}")
    print(f"structured: {json.dumps(structured(_client, _model, q, schema), ensure_ascii=False)}")


def main() -> None:
    s1_system_prompt()
    s2_few_shot()
    s3_chain_of_thought()
    s4_structured()


if __name__ == "__main__":
    main()
