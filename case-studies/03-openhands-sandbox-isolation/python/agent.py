"""agent.py —— LLM tool-calling agent, 把所有 shell 命令都跑在 sandbox 里.

跟 OpenHands 对照:
  - 真 OpenHands: App Server 收到 LLM 的 tool_call("bash", ...) →
                  POST /api/v1/events 到 sandbox 内的 Agent Server →
                  Agent Server 调 subprocess.Popen
  - Demo: 主进程的 ReAct loop 直接调 sandbox.exec_in_sandbox()
          省掉 HTTP 那一层, 但保留 session_api_key 鉴权
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable, Optional

import httpx
from dotenv import load_dotenv
from openai import OpenAI
from sandbox import ProcessSandbox, SandboxInfo

load_dotenv()


_http = httpx.Client(trust_env=False, timeout=60.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


# OpenAI function-calling 工具定义
BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command inside the sandbox. The command's cwd is the "
        "sandbox's isolated workspace. Use this to create files, run scripts, "
        "or inspect the workspace. NEVER use this to read paths outside the workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to run.",
                }
            },
            "required": ["command"],
        },
    },
}


@dataclass
class ToolCall:
    name: str
    args: dict
    result: str


def run_agent(
    sandbox_svc: ProcessSandbox,
    sandbox: SandboxInfo,
    user_task: str,
    max_iterations: int = 8,
    on_tool: Optional[Callable[[ToolCall], None]] = None,
) -> tuple[str, list[ToolCall]]:
    """跑一个最小 ReAct loop. 所有 bash 工具调用都进 sandbox.

    返回 (最终回答, 工具调用历史).
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are a coding assistant operating ONLY through the 'bash' tool inside a sandbox. "
                "RULES:\n"
                "1. You MUST use the bash tool for ALL file writes and code execution. "
                "Do NOT paste code in your reply text — write files with bash heredocs or echo, "
                "then run them with bash.\n"
                "2. Each step is ONE bash command. After seeing output, decide the next bash call.\n"
                "3. Only after you've actually run and verified the code, give a one-line summary.\n"
                "4. Never claim something works without having executed it via bash.\n"
                "The host machine is off limits; only the sandbox workspace is writable."
            ),
        },
        {"role": "user", "content": user_task},
    ]
    tool_history: list[ToolCall] = []

    for _ in range(max_iterations):
        resp = _client.chat.completions.create(
            model=_model,
            messages=messages,
            tools=[BASH_TOOL],
            temperature=0.3,
        )
        msg = resp.choices[0].message

        # 没工具调用 = 结束
        if not msg.tool_calls:
            return (msg.content or "", tool_history)

        # 把 assistant 整条消息(含 tool_calls)写回历史
        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        # 逐个执行工具
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            if tc.function.name == "bash":
                cmd = args.get("command", "")
                rc, stdout, stderr = sandbox_svc.exec_in_sandbox(
                    sandbox.id, sandbox.session_api_key, cmd
                )
                # 把命令结果做成观察
                if rc == 0:
                    observation = stdout or "(no output)"
                else:
                    observation = f"[exit {rc}]\nstdout: {stdout}\nstderr: {stderr}"
                call = ToolCall(name="bash", args=args, result=observation[:500])
                tool_history.append(call)
                if on_tool:
                    on_tool(call)
            else:
                observation = f"unknown tool: {tc.function.name}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": observation,
                }
            )

    # 跑满 iteration 还没结论, 强迫给个总结
    return ("(reached max iterations without final answer)", tool_history)
