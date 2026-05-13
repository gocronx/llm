"""Spawn the three specialist agents, run a demo request through the coordinator, then clean up."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

HERE = Path(__file__).resolve().parent

AGENTS = [
    ("translator",  int(os.getenv("TRANSLATOR_PORT", "8101"))),
    ("reviewer",    int(os.getenv("REVIEWER_PORT", "8102"))),
    ("summarizer",  int(os.getenv("SUMMARIZER_PORT", "8103"))),
]

DEMO_QUERIES = [
    "把这段中文翻译成英文：能否帮忙看一下这个错误日志，紧急。",
    "Review this Python code for security issues: subprocess.run(f'curl {user_input}', shell=True)",
    "Translate this to English AND check the code for security: "
    "原文：'请帮我审查这段代码：subprocess.run(user_input, shell=True)'",
    "把这段长文总结成 2 句话：人工智能的快速发展引发了广泛讨论。"
    "支持者认为它将提升生产力、解决复杂问题。反对者则担忧失业、隐私泄露和潜在的失控风险。"
    "无论立场如何，监管和伦理框架的建立已成为各国共识。",
]


def wait_for_health(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/health", timeout=1)
            if r.ok:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.3)
    return False


def spawn_agent(name: str, port: int) -> subprocess.Popen:
    print(f"  starting {name} on :{port} ...", end=" ", flush=True)
    proc = subprocess.Popen(
        [sys.executable, "-m", f"agents.{name}"],
        cwd=HERE,
        env={**os.environ, "AGENT_LOG_LEVEL": "warning"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if wait_for_health(port):
        print("up")
    else:
        print("TIMEOUT")
        proc.terminate()
        raise SystemExit(f"agent {name} failed to start")
    return proc


def main():
    print("=== A2A protocol demo ===\n")
    auth = "bearer token (AGENT_TOKEN set)" if os.getenv("AGENT_TOKEN") else "DISABLED (open)"
    print(f"Auth: {auth}")
    print("\nSpawning specialist agents...")
    procs: list[subprocess.Popen] = []
    try:
        for name, port in AGENTS:
            procs.append(spawn_agent(name, port))

        # 显示发现到的 agent cards
        print("\nDiscovered agents (via /.well-known/agent.json):")
        for _, port in AGENTS:
            card = requests.get(f"http://127.0.0.1:{port}/.well-known/agent.json").json()
            print(f"  - {card['name']:<12} caps={card['capabilities']}")

        # 跑 demo queries
        from coordinator import run_coordinator
        for i, q in enumerate(DEMO_QUERIES, 1):
            print(f"\n--- Query [{i}] {q[:60]}{'...' if len(q) > 60 else ''}")
            started = time.time()
            result = run_coordinator(q)
            elapsed = int((time.time() - started) * 1000)

            plan = result.get("plan", [])
            print(f"  plan: {len(plan)} task(s) → {[t.get('agent') for t in plan]}")
            for entry in result.get("results", []):
                resp = entry["response"]
                state = resp.get("state")
                if state == "completed":
                    out = resp.get("output", {})
                    preview = next(iter(out.values())) if out else ""
                    if isinstance(preview, list):
                        preview = f"<list of {len(preview)} items>"
                    preview = str(preview)[:120]
                    print(f"  ✓ {entry['agent']:<12} {preview}")
                else:
                    print(f"  ✗ {entry['agent']:<12} failed: {resp.get('error')}")
            print(f"  total: {elapsed}ms")
    finally:
        print("\nShutting down agents...")
        for p in procs:
            p.send_signal(signal.SIGTERM)
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print("done.")


if __name__ == "__main__":
    main()
