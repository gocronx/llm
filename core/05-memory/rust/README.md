# 05 · Memory Management (Rust)

| 文件 | 角色 |
|---|---|
| `src/memory.rs` | 🟢 `Full / Window / Tokens / Summary` 都实现 `Memory` trait |
| `src/chat.rs` | 🟢 `ask()` + `make_summarizer()` 工厂 |
| `src/main.rs` | demo only |

## 怎么跑

```bash
cd rust && cargo run
```

## 关键设计点

- `Memory` trait + 泛型 `M: Memory`，调用方不关心具体策略
- `SummarizeFn = Box<dyn Fn>` —— 注入式 summarizer，便于测试和复用
- Summary 累积叠加（旧事实不能丢）
- Tokens 至少留 1 条（不能全清空）

## 同 Python/Go 版相同的坑

- ❌ Summary 直接覆盖旧摘要
- ❌ Tokens 清空所有 msg
- ❌ system prompt 算进 Window 长度
