# 10 · Multi-Agent (Go)

| 文件 | 角色 |
|---|---|
| `agent.go` | 🟢 `Agent.Execute(task, context)` |
| `orchestrator.go` | 🟢 `RunSequential` / `RunParallel` / `Step` |
| `main.go` | demo only |

## 怎么跑

```bash
cd go && go mod tidy && go run .
```

## 同 Python 版的设计点

- `Agent.Execute(ctx, task, extra)`，extra 是上游产物
- `RunSequential` 走依赖，`RunParallel` 并发（用 goroutine + WaitGroup）
- `buildContext` 截断（maxCtxChars=400），防爆 context
- 并行不解 DAG，调用方保证 steps 独立

## 常见坑

- ❌ 拼依赖时不截断 → context 爆
- ❌ 并行 step 之间有依赖 → 拿不到上游产物
- ⚠️ `sync.Mutex` 别忘了，多 goroutine 写 map 会 race
