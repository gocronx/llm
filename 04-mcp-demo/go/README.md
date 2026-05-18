# 04 · MCP (Go) — 手撸 MCP-stdio 客户端 + go-openai 桥接

**Go 这边没有官方 MCP SDK，自己写一个就 100 行：JSON-RPC 2.0 over NDJSON。**
**关键卖点：Go client 拉起 Python server，跨语言透明 —— 这正是 MCP 想解决的事。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `mcp.go` | 🟢 套出去用 | `MCPClient`：拉子进程、握手、tools/list、tools/call |
| `client.go` | 🟢 套出去用 | `Bridge`：MCP tools ↔ OpenAI tools，多轮 chat 循环 |
| `main.go` | demo only | 拉 `../python/server.py`，让 LLM 操作 todo.txt |

## MCP-stdio 协议（够用版）

| 步骤 | client → server | server → client |
|---|---|---|
| 握手 | `initialize` (id=1) | `result: serverInfo + capabilities` |
| 完成 | `notifications/initialized` | (无回响应) |
| 列工具 | `tools/list` (id=2) | `result: { tools: [...] }` |
| 调工具 | `tools/call {name, arguments}` (id=3) | `result: { content: [{type, text}], isError }` |

每条消息一行 JSON，stdout 是协议通道 —— server 千万别 print 调试信息到 stdout。

## 怎么跑

```bash
# 先确保 Python server 能跑（装好 mcp 包）
cd ../python && pip install -r requirements.txt && cd -

cd go
go mod tidy
go run .
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| 用 `sync.Map` 风格的 pending map | 多个 in-flight 请求要按 id 路由响应；不能假设 server 严格按顺序回 |
| `bufio.Scanner` buffer 调大到 4MB | tools/list 可能把 schema 都塞进来，默认 64KB 不够 |
| `MCPClient.Close()` 关 stdin 后 Wait | 关 stdin 让 server 自己 EOF 退出；Wait 收尸防僵尸进程 |
| `notifications/initialized` 没 id | JSON-RPC 通知不带 id，server 不回 —— 写 client 时容易忘 |

## 常见坑

- ❌ **Server.py print 到 stdout** —— stdout 是协议通道，一行 print 就破坏帧；调试输出走 stderr
- ❌ **Scanner 默认 64KB buffer** —— tools/list 响应里 schema 大点就截断，看似"无响应"
- ❌ **不发 `notifications/initialized`** —— Python MCP server 会拒绝后续请求
- ❌ **不 Close MCPClient** —— Python 子进程僵尸进程泄漏
- ⚠️ **协议版本** —— 这里用 `2024-11-05`；MCP 一直在更新，要看 server 端 SDK 版本兼容哪些
