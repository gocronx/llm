"""main.py —— demo only：跑 datasets/qa_testset.jsonl，输出报告。"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from runner import load_jsonl, print_report, run

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=60.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


def main() -> None:
    samples = load_jsonl(Path(__file__).parent.parent / "datasets" / "qa_testset.jsonl")
    print(f">>> 跑 {len(samples)} 个样本")
    rep = run(_client, _model, samples, workers=4)
    print_report(rep)


if __name__ == "__main__":
    main()
