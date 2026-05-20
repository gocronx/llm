"""server.py —— 一个真正的 MCP server，走 stdio 传输，提供 3 个文件系统工具。
整文件 cp 进项目即可（改 tool 实现 + 改 base_path）。

MCP 的核心抽象：server 暴露一组 tools/resources/prompts，client 通过 JSON-RPC
来发现和调用。stdio 是最简单的传输：client 把 server 当子进程拉起来，
stdin/stdout 跑 NDJSON 协议。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# base_path 通过 CLI 第一个参数传入；默认当前目录下的 test_workspace。
# 用 resolve() 早早算出绝对路径，避免 LLM 写 "../../etc/passwd" 这种逃逸。
BASE = Path(sys.argv[1] if len(sys.argv) > 1 else "test_workspace").resolve()
BASE.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("filesystem-server")


def _safe(rel: str) -> Path:
    """把相对路径绑死在 BASE 下；超出范围直接 raise。"""
    p = (BASE / rel).resolve()
    if not str(p).startswith(str(BASE)):
        raise ValueError(f"path escapes sandbox: {rel}")
    return p


@mcp.tool()
def read_file(path: str) -> str:
    """读取文本文件内容。"""
    return _safe(path).read_text(encoding="utf-8")


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """写入文本文件，自动建父目录。"""
    p = _safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} chars to {path}"


@mcp.tool()
def list_directory(path: str = ".") -> str:
    """列目录，返回 name + 类型 + 字节大小，每行一个。"""
    d = _safe(path)
    if not d.is_dir():
        return f"not a directory: {path}"
    lines = []
    for item in sorted(d.iterdir()):
        if item.is_dir():
            lines.append(f"dir   {item.name}/")
        else:
            lines.append(f"file  {item.name}  {item.stat().st_size}B")
    return "\n".join(lines) if lines else "(empty)"


if __name__ == "__main__":
    # FastMCP.run() 默认 stdio 传输；不会 print 任何东西到 stdout（stdout 留给协议）。
    mcp.run()
