# 04 · MCP (Rust) — 手撸 MCP-stdio 客户端 + ureq

**没有官方 Rust MCP SDK，自己写一个 130 行的同步 stdio 客户端。Rust 拉起 Python server，跨语言透明跑通。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `src/mcp.rs` | 🟢 套出去用 | `MCPClient::spawn`、握手、`list_tools`、`call_tool` |
| `src/client.rs` | 🟢 套出去用 | OpenAI ↔ MCP 桥接，多轮 chat 循环 |
| `src/main.rs` | demo only | 拉 `../python/server.py`，让 LLM 操作 todo.txt |

## 怎么跑

```bash
# 先确保 Python server 能跑（装好 mcp 包）
cd ../python && pip install -r requirements.txt && cd -

cd rust
cargo run
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| 同步阻塞 IO 不引 tokio | LLM 调 tool 串行，单线程够用；引入 tokio 整套链就变重了 |
| `recv()` 循环里跳过非匹配 id 的消息 | server 可能在响应之间发通知；按 id 匹配最稳 |
| `Drop` 关 stdin 并 `wait()` | 防 Python 子进程僵尸；不 wait 系统会留 zombie |
| `stderr(Stdio::inherit())` | server 的调试输出（如果有）直接进我们的 stderr，方便看 |

## 常见坑

- ❌ **`recv()` 假设响应严格按发送顺序** —— server 可能插通知，必须按 id 匹配
- ❌ **`MCPClient` Drop 不收尸** —— Python 子进程僵尸，跑几次系统就慢
- ❌ **`read_line` 不区分 0 字节** —— `read_line` 返回 0 表示 EOF，要显式判断
- ⚠️ **跨平台的 `python3` 命令** —— Windows 上 python 不一定叫 `python3`；生产里用 `which python` 或显式路径
