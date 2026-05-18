# 04 · MCP (Python) — `FastMCP` server + `ClientSession` over stdio

**MCP 的核心：把工具定义从应用里抽出来放进 server，server 单独跑、单独升级，**
**多个 client 复用同一份工具实现。本 demo 是真协议跑通，不是把工具内联进 client。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `server.py` | 🟢 套出去用 | `FastMCP` 装饰器声明工具，stdio 传输 |
| `client.py` | 🟢 套出去用 | `MCPBridge` 把 MCP server 桥接成 OpenAI tools |
| `main.py` | demo only | 让 LLM 通过 MCP 创建并读回 todo.txt |
| `test.py` | demo only | 协议级测试（不依赖 LLM） |

## 数据流

```
main.py / test.py
    └─ MCPBridge (在 client.py)
         ├─ stdio_client 拉起 python server.py 子进程
         ├─ initialize 握手
         ├─ tools/list  →  转成 OpenAI tools schema
         └─ for tool_call from LLM:
              tools/call(name, args) → 拿到 result → 回灌 LLM
```

`server.py` 全程不打 stdout —— stdout 是给协议用的，print 一行 server 就崩。

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py     # 协议级测试，不需要 LLM
python main.py     # 让 LLM 实际通过 MCP 操作文件
```

`test.py` 期待输出：

```
✓ list_tools -> ['list_directory', 'read_file', 'write_file']
✓ write+read round-trip
✓ list_directory sees hello.txt

3/3 passed
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| `FastMCP` 而不是原生 `Server` | 装饰器写法，工具实现 = Python 函数，无需手写 Tool/InputSchema |
| 把 server 当子进程拉起 | stdio 传输最简单；生产里也可以换 HTTP / SSE，client 接口不变 |
| `_safe()` 把路径绑死在 BASE | LLM 拿到 `write_file` 后想写 `/etc/passwd` 是常态，沙箱必须有 |
| `MCPBridge` 用 `AsyncExitStack` | stdio_client 和 ClientSession 都是 async ctx；用栈统一 close，崩了不漏进程 |
| `chat()` 多轮循环 | LLM 可能先 list_directory 再 write_file 再 read_file，单轮不够 |

## 常见坑

- ❌ **server.py 里 print 到 stdout** —— stdout 是协议通道，打一行就破坏 JSON-RPC 帧；调试输出走 stderr
- ❌ **没设沙箱** —— 暴露给 LLM 的 read_file/write_file 必须限定根目录，否则 `../../etc/passwd` 就出去了
- ❌ **client 用完不 close** —— 子进程会泄漏，用 `AsyncExitStack` 或 `async with`
- ❌ **`tools/list` 的 schema 直接喂 LLM** —— MCP 用 `inputSchema`，OpenAI 用 `parameters`，要做一次字段名转换
- ⚠️ **MCP SDK 版本** —— 1.10+ 才有稳定 `FastMCP`；老版本（0.9.x）API 完全不同
