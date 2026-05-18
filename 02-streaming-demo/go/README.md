# 02 · Streaming (Go) — `sashabaranov/go-openai` 流式 API

**SDK 的 `CreateChatCompletionStream` 已经把 SSE 分帧 / `[DONE]` 哨兵处理掉，应用层只 `stream.Recv()` 直到 `io.EOF`。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `client.go` | 🟢 套出去用 | `StreamText` 纯文本；`StreamWithTools` 流式+工具 |
| `tools.go` | 🟢 套出去用（自己改） | 同 01 的 registry 写法 |
| `main.go` | demo only | 两个场景的入口 |

## 怎么跑

```bash
cd go
go mod tidy
go run .
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| 用 SDK 的 stream 而不是手撸 net/http + bufio | SDK 帮你处理 `data: ` 前缀 / `[DONE]` / keep-alive 行 |
| `ToolCall.Index` 是 `*int` | 流式 chunk 才会带 index；非流式 message 里 Index 为 nil。按 index 分槽位 |
| `Arguments` 字符串拼接，最后再 unmarshal | 半截 JSON 不是合法对象，不能边收边解析 |
| onTool / onDelta 回调 | 调用方决定怎么渲染（CLI 直接 print，Web 推 SSE，TUI 走 channel） |

## 常见坑

- ❌ **手撸 `bufio.Reader` 读 SSE** —— `data: \n\n` 分帧、`: keep-alive` 注释、`[DONE]` 哨兵都得处理，SDK 已经做好
- ❌ **`tc.Index` 当成 `int` 用** —— 解引 nil 指针会 panic，先 `if tc.Index != nil`
- ❌ **`Arguments` 边收边 `json.Unmarshal`** —— 永远报 unexpected end of JSON input
- ❌ **`stream.Close()` 忘了** —— 连接泄漏，本 demo 用 `defer second.Close()`；第一轮因为要在中途切到第二轮所以手动 `Close()`
