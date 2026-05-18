# 03 · Structured Output — `response_format: json_schema` + `strict: true`

**让 OpenAI 在 token 解码阶段就按 JSON Schema 做约束，返回的就是合法 JSON 且字段类型/枚举严格匹配。不再需要"prompt 求模型返回 JSON，再 try/except parse"那种 50% 翻车率的写法。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `client.py` | 🟢 套出去用 | `extract(client, model, system, user, schema)` 返回 dict |
| `schemas.py` | 🟢 套出去用（自己改） | 三个示例 schema：嵌套对象、enum、必填字段 |
| `main.py` | demo only | 三个场景 |
| `test.py` | demo only | 验证 required / 嵌套类型 / enum 落点 |

## strict 模式的硬性规则

OpenAI 的 strict 不是"宽松解析"，是 **schema 违规直接 400**。三条必守：

1. **每个 object 都要 `additionalProperties: false`**（哪怕嵌套对象）
2. **`required` 必须列出 `properties` 里所有 key** —— strict 不允许"可选字段"，要可选就把字段类型改成 `["string", "null"]`
3. **不支持 `default` / `format: email` / 大部分 `pattern`** —— 用 `enum` 或文档约束

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python main.py
python test.py
```

期待输出：

```
>>> 简历提取
{ "name": "张三", "age": 28, "position": "Python 工程师",
  "email": "zs@example.com", "skills": ["Django", "FastAPI", "PostgreSQL"] }
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| `strict: true` 而不是 `type: "json_object"` | `json_object` 只保证"是合法 JSON"，不保证 schema；strict 保证 schema |
| schema 独立放 `schemas.py` | schema 是数据不是行为，main / test 复用同一份；改 schema 不动 client |
| 直接 `json.loads`，不 try/except | strict 模式 parse 失败就是网关 bug，要修不要 swallow |
| enum 限定输出域 | 情感分类这种"只能是 A/B/C"的场景比 prompt 里写"只能输出 positive/neutral/negative"靠谱 |

## 常见坑

- ❌ **嵌套对象忘了 `additionalProperties: false`** —— OpenAI 直接 400 报 schema 不合法
- ❌ **`required` 没列全字段** —— strict 不允许可选；要"可选"用 `["type", "null"]`
- ❌ **schema 里写 `format: "email"`** —— OpenAI strict 不认 format，会报 400
- ❌ **prompt 还在写"请返回 JSON"** —— 多此一举，response_format 已经强制了
- ⚠️ **本地模型未必支持 json_schema** —— MLX / vLLM 看具体版本，部分只支持 `json_object`；这种时候 strict 没法跨平台 transparently 用
