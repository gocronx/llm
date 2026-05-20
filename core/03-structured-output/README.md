# 03 · Structured Output Demo

三语言对照：用 `response_format: json_schema` + `strict: true` 让 LLM 必须按 JSON Schema 返回，从 token 解码阶段就做约束。

## 为什么不靠 prompt

"请返回 JSON" + try/except json.loads + 处理 markdown 包裹是上一个时代的活。strict 模式让模型在 token 解码时只能输出符合 schema 的 token —— 不再有 JSON 解析失败、字段名拼错、类型不对的问题。

代价：**schema 写错就直接 400**（strict 不会"宽松降级"）。三条硬规则记牢：

1. 每个 object 都要 `additionalProperties: false`
2. `required` 必须列全 properties 里的 key（要可选用 `["string", "null"]`）
3. 不支持 `default` / `format: email` / 大多数 `pattern`

## 目录

```
.
├── .env             # API_BASE_URL / API_KEY / MODEL_ID
├── python/          # OpenAI SDK + response_format
├── go/              # go-openai v1.32+ JSONSchema 字段
└── rust/            # ureq + 直拼 JSON
```

## 跑起来

```bash
# Python
cd python && pip install -r requirements.txt && python main.py

# Go
cd go && go mod tidy && go run .

# Rust
cd rust && cargo run
```

## 三个场景

| 场景 | schema 形态 | 演示什么 |
|---|---|---|
| 简历提取 | object + array | required 字段 + 数组类型 |
| 产品信息 | 嵌套 object + enum | 嵌套也得 additionalProperties:false；currency enum 锁值域 |
| 情感分类 | object + label enum | 用 enum 而不是 prompt 限定输出域，省 prompt 长度也更靠谱 |

## 共通的坑

- ❌ **嵌套 object 漏 `additionalProperties: false`** —— OpenAI 直接 400
- ❌ **`required` 不写全** —— strict 不允许"可选"
- ❌ **prompt 还在求 JSON** —— 多此一举，且容易和 schema 冲突
- ⚠️ **本地模型未必支持 json_schema** —— MLX / vLLM 老版本可能只支持 `json_object`，这种时候只能退而求其次（"json_object" 只保证合法 JSON，不保证 schema）
