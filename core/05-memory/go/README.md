# 05 · Memory Management (Go) — 四种策略，同接口

| 文件 | 角色 |
|---|---|
| `memory.go` | 🟢 `Full / Window / Tokens / Summary` 四种策略，都实现 `Memory` 接口 |
| `chat.go` | 🟢 `Chat`：memory + LLM 客户端；`MakeSummarizer` 工厂 |
| `main.go` | demo only |

## 怎么跑

```bash
cd go && go mod tidy && go run .
```

## 同 Python 版的设计点

- 四种策略共享 `Memory` interface，`Chat` 不关心是哪种
- `Summary` 的 `SummarizeFn` 是函数类型，注入而不是 hardcode 依赖
- `Summary` 累积叠加摘要，不覆盖
- `EstimateTokens` 糙估，生产换 tiktoken-go

## 常见坑（同 Python）

- ❌ Summary 直接覆盖旧摘要 → 旧事实丢
- ❌ Tokens 把 msg 全清光 → 模型完全失忆
- ❌ system prompt 被算进 Window 长度
- ⚠️ 中文 token 估算糙，仅供 demo
