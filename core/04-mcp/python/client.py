"""client.py —— MCP client：拉起 server 子进程，把它的工具桥接给 LLM。
整文件 cp 进项目即可（改 server 命令、把 OpenAI 客户端换成你自己的）。

干的就一件事：MCP 协议下的 `tools/list` -> 转成 OpenAI 的 `tools` 字段；
LLM 决定 `tool_calls` -> 通过 MCP 的 `tools/call` 执行 -> 把结果回灌 LLM。
"""
from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI


class MCPBridge:
    """把一个 MCP server 桥接成 OpenAI 兼容的 tools 接口。
    使用方式：`async with MCPBridge(cmd, args) as bridge:`，里面 bridge.chat(llm, model, msg)"""

    def __init__(self, command: str, args: list[str]):
        self._params = StdioServerParameters(command=command, args=args)
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: list[dict] = []  # OpenAI 格式

    async def __aenter__(self):
        # stdio_client 是 async context manager；进栈拿读写流
        read, write = await self._stack.enter_async_context(stdio_client(self._params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        # 把 MCP 的 Tool 列表翻译成 OpenAI 的 tools schema
        listed = await self._session.list_tools()
        self._tools = [
            {"type": "function", "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.inputSchema or {"type": "object", "properties": {}},
            }} for t in listed.tools
        ]
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._stack.aclose()

    @property
    def tools(self) -> list[dict]:
        return self._tools

    async def call(self, name: str, args: dict[str, Any]) -> str:
        """跑一次 MCP tools/call，把结果序列化成字符串给 LLM。"""
        assert self._session is not None
        result = await self._session.call_tool(name, args)
        # 结果是 list[TextContent|ImageContent|...]；这里只取 text 拼起来
        parts = [c.text for c in result.content if getattr(c, "type", None) == "text"]
        out = "\n".join(parts) if parts else json.dumps([c.model_dump() for c in result.content])
        return out

    async def chat(self, client: OpenAI, model: str, user_msg: str, max_rounds: int = 6) -> str:
        """LLM ↔ MCP tools 多轮循环，直到 LLM 不再 call tool 为止。"""
        messages: list[dict] = [{"role": "user", "content": user_msg}]
        for _ in range(max_rounds):
            resp = client.chat.completions.create(
                model=model, messages=messages, tools=self.tools,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return msg.content or ""

            messages.append(msg.model_dump(exclude_none=True))
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                result = await self.call(tc.function.name, args)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        return "(max rounds reached)"


# 同步 wrapper：把 asyncio.run 藏掉，main.py / test.py 调用更顺
def run_sync(command: str, args: list[str], client: OpenAI, model: str, user_msg: str) -> str:
    async def go() -> str:
        async with MCPBridge(command, args) as bridge:
            return await bridge.chat(client, model, user_msg)
    return asyncio.run(go())
