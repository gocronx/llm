"""Walk five scenarios through resolve_refs + render_for_llm."""

import os
from pathlib import Path

import requests
from colorama import Fore, Style, init
from dotenv import load_dotenv

from refs import WORKSPACE, render_for_llm, resolve_refs

init(autoreset=True)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


SCENARIOS: list[tuple[str, bool]] = [
    ("我的代码 @user.py 里 find_user 有什么问题？", True),
    ("@api.py:5-15 这几行有什么风险？", True),
    ("结合 @notes.md 和 @api.py，列出需要做的 TODO 是什么，按优先级排。", True),
    ("审查这段：@nonexistent.py 文件还在吗？", False),
    ("这是单纯的问题：解释一下闭包是什么。", True),
]


def call_llm(prompt: str, max_tokens: int = 400) -> str:
    resp = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def main() -> None:
    print(f"{Fore.CYAN}@-ref demo{Style.RESET_ALL}")
    print(f"workspace = {WORKSPACE}")
    print("files:")
    for p in sorted(WORKSPACE.iterdir()):
        print(f"  - {p.name}")

    for i, (message, call) in enumerate(SCENARIOS, 1):
        print(f"\n{Fore.CYAN}=== scenario {i} ==={Style.RESET_ALL}")
        print(f"user message: {message}")

        refs, files = resolve_refs(message)
        print(f"  refs detected: {len(refs)}  files actually read: {len(files)}")
        for r in refs:
            tag = "  ✓" if not r.error else f"  ✗ {r.error}"
            print(f"    - {r.raw:<24} → {r.path or '(invalid)'}{tag}")

        if not call:
            print("  (LLM call skipped)")
            continue

        prompt = render_for_llm(message, refs)
        try:
            answer = call_llm(prompt)
            preview = answer[:240] + ("..." if len(answer) > 240 else "")
            print(f"  {Fore.GREEN}answer:{Style.RESET_ALL} {preview}")
        except Exception as e:
            print(f"  {Fore.RED}error:{Style.RESET_ALL} {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
