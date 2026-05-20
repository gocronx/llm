# 10 · Multi-Agent (Rust)

| 文件 | 角色 |
|---|---|
| `src/agent.rs` | 🟢 `Agent::execute(task, extra)` |
| `src/orchestrator.rs` | 🟢 `run_sequential` / `run_parallel` |
| `src/main.rs` | demo only |

## 怎么跑

```bash
cd rust && cargo run
```

## 设计点

- 并行用 `std::thread` —— 不引 tokio，ureq 是同步阻塞，thread 就够
- `Arc<HashMap<String, Agent>>` 跨线程共享 agents
- `Mutex<HashMap>` 收并行结果
- `build_context` 按字符（不是字节）截断，否则中文会乱码

## 常见坑

- ❌ 按字节切中文 → 半个字符崩 unwrap
- ❌ `Arc<Mutex<...>>` 用完忘解锁导致死锁（用 RAII 自动释放）
- ⚠️ ureq 阻塞，并行 N 个 step 就开 N 个线程；高并发改 reqwest+tokio
