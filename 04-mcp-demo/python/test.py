"""test.py —— 不依赖 LLM 的协议级测试：
直接走 MCP 协议把 server 拉起来，list/call 检查 read/write/list_directory 三个工具都能用。"""
from __future__ import annotations

import asyncio
import os
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run() -> int:
    workspace = os.path.abspath("test_workspace")
    os.makedirs(workspace, exist_ok=True)

    params = StdioServerParameters(command=sys.executable, args=["server.py", workspace])
    passed = 0
    async with AsyncExitStack() as stack:
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        tools = (await session.list_tools()).tools
        names = sorted(t.name for t in tools)
        ok = names == ["list_directory", "read_file", "write_file"]
        print(f"{'✓' if ok else '✗'} list_tools -> {names}")
        passed += int(ok)

        await session.call_tool("write_file", {"path": "hello.txt", "content": "hi mcp"})
        out = (await session.call_tool("read_file", {"path": "hello.txt"})).content[0].text
        ok = "hi mcp" in out
        print(f"{'✓' if ok else '✗'} write+read round-trip")
        passed += int(ok)

        listing = (await session.call_tool("list_directory", {"path": "."})).content[0].text
        ok = "hello.txt" in listing
        print(f"{'✓' if ok else '✗'} list_directory sees hello.txt")
        passed += int(ok)

    print(f"\n{passed}/3 passed")
    return 0 if passed == 3 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
