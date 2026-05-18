"""main.py —— demo only：5 个场景过 resolve_refs → render_for_llm → 调 LLM。"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from refs import WORKSPACE, render_for_llm, resolve_refs

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_http = httpx.Client(trust_env=False, timeout=120.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


# (message, 是否真调 LLM)
SCENARIOS: list[tuple[str, bool]] = [
    ("我的代码 @user.py 里 find_user 有什么问题？", True),
    ("@api.py:5-15 这几行有什么风险？", True),
    ("结合 @notes.md 和 @api.py，列出需要做的 TODO 是什么，按优先级排。", True),
    ("审查这段：@nonexistent.py 文件还在吗？", False),
    ("这是单纯的问题：解释一下闭包是什么。", True),
]


def ask(prompt: str) -> str:
    resp = _client.chat.completions.create(
        model=_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=400,
    )
    return (resp.choices[0].message.content or "").strip()


def main() -> None:
    print("@-ref demo")
    print(f"workspace = {WORKSPACE}")
    print("files:")
    for p in sorted(WORKSPACE.iterdir()):
        print(f"  - {p.name}")

    for i, (msg, call) in enumerate(SCENARIOS, 1):
        print(f"\n=== scenario {i} ===")
        print(f"user message: {msg}")

        refs, files = resolve_refs(msg)
        print(f"  refs detected: {len(refs)}  files actually read: {len(files)}")
        for r in refs:
            mark = "✓" if not r.error else f"✗ {r.error}"
            print(f"    - {r.raw:<24} → {r.path or '(invalid)'}  {mark}")

        if not call:
            print("  (LLM call skipped)")
            continue

        prompt = render_for_llm(msg, refs)
        try:
            answer = ask(prompt)
            preview = answer[:240] + ("..." if len(answer) > 240 else "")
            print(f"  answer: {preview}")
        except Exception as e:
            print(f"  error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
