# 01 · LLM Function Call (Rust) — `ureq` + 两轮往返

**Rust 版 slim：保留 `ureq` 同步请求（同原版），重写工具注册表 + 两轮交互一共 276 行（原版 647 行）。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `src/client.rs` | 🟢 套出去用 | `run(&cfg, user_msg)` 一次完成两轮交互 |
| `src/tools.rs` | 🟢 套出去用（自己改） | `Tool { name, schema, call }` 结构体；`all()` 是工具清单 |
| `src/main.rs` | demo + verify | 默认 demo；`cargo run -- verify` 验证 |

## 怎么跑

```bash
cd rust_slim
cargo run             # demo
cargo run -- verify   # 验证调对了工具
```

## 行数对比

| 文件 | 原版 | slim |
|---|---|---|
| 工具定义 | `functions.rs` 316 | `tools.rs` 136 |
| 主入口 | `main.rs` 184 | `main.rs` 75 + `client.rs` 65 |
| 测试 | `test.rs` 147 | （并到 `main.rs verify`） |
| **总计** | **647** | **276** |

砍掉的：
- 大段 `HashMap<&str, HashMap<&str, Value>>::from([(...), (...)])` 字面量构造 —— 用 `match` 表达式表 + tuple 替代，省 3/4 行
- `parse_price_query` 字符串扫描 + 中文关键词匹配 —— LLM 自己拆参数
- 原版每个文件都自己 `dotenv().ok()` + `env::var()` 三次 —— slim 在 main 入口一次性建 `Config` 传下去
- 原版 `Message` 七个 `Option<...>` 字段全靠 `#[serde(skip_serializing_if)]` —— slim 用 `serde_json::Value` 在客户端就近构造，省掉数据结构定义

## 关键设计点

| 决策 | 原因 |
|---|---|
| `Tool { call: fn(Value) -> Value }` | 用普通函数指针而不是 `Box<dyn Fn>`，零开销且 Sync。Rust 没装饰器，但 `all()` 函数返回 `vec![weather(), calculate(), ...]` 同样实现"加工具改一处" |
| 用 `serde_json::Value` 而不是定义 `Message`/`ToolCall` struct | 这是 demo 不是 SDK，wire format 用 Value 直接构造省去 7 个 `#[derive]` struct 和无数 `Option<...>` |
| `ureq` 同步而非 `reqwest` 异步 | 单线程跑两次 HTTP，async runtime 是过度工程 |

## 加新工具

在 `tools.rs` 的 `all()` 里加一项，写一个 `fn xxx() -> Tool`：

```rust
fn send_email() -> Tool {
    Tool {
        name: "send_email",
        schema: json!({
            "name": "send_email",
            "description": "发邮件",
            "parameters": {
                "type": "object",
                "properties": {
                    "to":      {"type": "string"},
                    "subject": {"type": "string"},
                    "body":    {"type": "string"},
                },
                "required": ["to", "subject", "body"]
            }
        }),
        call: |args| {
            let to = args["to"].as_str().unwrap_or("");
            // ... 实际发邮件
            json!({"sent": true, "to": to})
        },
    }
}
```

然后把 `send_email()` 加进 `all()` 的 `vec![...]`，完事。

## 常见坑

- ❌ **闭包想 capture 状态** —— `fn(Value) -> Value` 不能 capture。如果你的工具要持有 db 连接之类的状态，把 `call` 字段改成 `Box<dyn Fn(Value) -> Value + Send + Sync>` 并在 `all()` 里 `Box::new(move |args| { ... })`
- ❌ **`ureq::send_json(&body)` vs `send_json(body)`** —— clippy 警告 `needless_borrows_for_generic_args`，去掉 `&` 即可
- ❌ **`as_f64()` 默认 0.0 把 b=0 当除零** —— slim 在 calculate 里区分 `op == "div" && b == 0.0` 显式返回 error，避免 `f64 / 0.0 = inf`
