# 03 · Structured Output (Go) — `go-openai v1.32+` JSONSchema response format

**`ResponseFormat.JSONSchema.Strict = true`，OpenAI 在解码时做约束，Content 一定是合法 JSON。无需 prompt 求 JSON / 无需 try-unmarshal-fallback。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `client.go` | 🟢 套出去用 | `Extract(...)` 给 schema、unmarshal 到 out |
| `schemas.go` | 🟢 套出去用（自己改） | `obj(props, required)` 帮你少写 additionalProperties |
| `main.go` | demo only | 三个场景 |

## 怎么跑

```bash
cd go
go mod tidy
go run .
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| `Schema` 字段用 `json.RawMessage` | go-openai 要求 `json.Marshaler`，RawMessage 是最轻的实现 |
| `obj()` helper 自动塞 `additionalProperties:false` | strict 模式硬要求，写多了容易漏 |
| `Extract(..., out any)` 用指针 | 调用方可以传 `*map[string]any` 也可以传具体 struct 指针 |
| go-openai 版本要 v1.30+ | v1.27 还没有 `ChatCompletionResponseFormatTypeJSONSchema` |

## 常见坑

- ❌ **`go-openai` 老版本（<1.30）** —— 没有 JSONSchema 常量，得自己拼 raw HTTP；升级最省事
- ❌ **嵌套 object 忘加 `additionalProperties:false`** —— OpenAI 直接 400
- ❌ **`required` 漏字段** —— strict 不允许可选；要可选用 `type: ["string", "null"]`
- ⚠️ **`Schema` 字段是 `json.Marshaler` 不是 `any`** —— 直接传 `map[string]any` 编译过不了，必须 `json.RawMessage(jsonBytes)`
