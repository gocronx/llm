# 02 · Streaming (Rust) — `ureq` 同步 + 手撸 SSE

**Rust 没有官方 OpenAI SDK，ureq 也不解 SSE。`each_sse` 就 20 行：按行读，拆 `data: ` 前缀，遇 `[DONE]` 停。client.rs 整文件 cp 出去就能用。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `src/client.rs` | 🟢 套出去用 | `stream_text` / `stream_with_tools` / `each_sse` |
| `src/tools.rs` | 🟢 套出去用（自己改） | 同 01 的 registry 写法 |
| `src/main.rs` | demo only | 两个场景 |

## 怎么跑

```bash
cd rust
cargo run
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| ureq 同步 + 手撸 SSE | 不引入 tokio + async-openai 的 reactor 链；20 行解析够用 |
| `Accept: text/event-stream` 显式带上 | 有些网关默认认 application/json 不给流 |
| `BTreeMap<u64, ...>` 累积 tool_calls | 按 `index` 分槽位且有序遍历，不依赖插入顺序 |
| `arguments` 用 `push_str` 拼接 | 半截 JSON 不是合法对象，必须等流读完再 `serde_json::from_str` |
| `Event` enum 而不是直接 print | 调用方决定 CLI / Web / TUI 怎么渲染 |

## 常见坑

- ❌ **把 `arguments` 当 dict 增量解析** —— 永远报 `EOF while parsing`
- ❌ **`stream_text` 错过 `tool_calls`** —— 流式 `delta` 可能里只有 tool_calls 没有 content，用 `as_str()` 取 content 时要允许 None
- ❌ **不带 `Accept: text/event-stream`** —— 某些网关/反代会把响应缓存成整段而不是流
- ⚠️ **ureq 是同步阻塞** —— stream 期间线程是占住的，Web 服务里要放进 thread pool（或换 reqwest + tokio）
