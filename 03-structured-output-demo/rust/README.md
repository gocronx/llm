# 03 · Structured Output (Rust) — ureq + 直拼 `response_format`

**Rust 没有官方 OpenAI SDK，ureq 同步直接拼 JSON。`response_format.json_schema.strict=true` 让模型在解码时按 schema 约束输出。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `src/client.rs` | 🟢 套出去用 | `extract(cfg, system, user, name, schema)` |
| `src/schemas.rs` | 🟢 套出去用（自己改） | `obj(properties, required)` 帮你少写 additionalProperties |
| `src/main.rs` | demo only | 三个场景 |

## 怎么跑

```bash
cd rust
cargo run
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| 直接发 `serde_json::Value` 不走 SDK | Rust 这边没有"事实标准 SDK"，ureq + Value 是最轻的栈 |
| `obj(props, required)` helper | strict 模式硬要求 additionalProperties:false + required 列全，写多了容易漏 |
| `extract` 返回 `Result<Value, String>` | parse 失败也带原始 raw，方便看哪里坏了 |

## 常见坑

- ❌ **嵌套 object 忘加 `additionalProperties: false`** —— OpenAI 直接 400
- ❌ **`required` 漏字段** —— strict 不允许可选；要可选用 `type: ["string", "null"]`
- ❌ **content 不是合法 JSON** —— 极小概率发生，说明本地模型没真支持 strict（多见于老版本 vLLM / 部分 MLX 实现）
