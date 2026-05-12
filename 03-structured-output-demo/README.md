# 结构化输出演示

结构化输出保证 LLM 的输出 100% 符合 JSON Schema，比 Prompt Engineering 更可靠。

**核心价值：格式保证、类型安全、生产可用**

**三语言实现：Python、Go、Rust**

---

## 什么是结构化输出

### 问题

**普通 JSON 输出的问题：**
```python
# 可能的输出
"```json\n{\"name\": \"张三\", \"age\": \"28\"}\n```"  # markdown 格式
"{姓名: 张三, 年龄: 28}"  # 字段名不一致
"{\"name\": \"张三\"}"  # 缺少必需字段
```

**结构化输出的保证：**
```python
# 保证的输出
'{"name": "张三", "age": 28, "email": "..."}'  # 纯 JSON
# - 字段名严格匹配
# - 类型严格匹配
# - 必需字段保证存在
```

---

## 快速开始

### Python 版本

```bash
cd python
pip install -r requirements.txt

# 1. 对比演示
python compare.py

# 2. 数据提取
python examples/data_extraction.py

# 3. 表单填充
python examples/form_filling.py

# 4. API 响应
python examples/api_response.py
```

### Go 版本

```bash
cd go
go mod tidy

# 结构化输出演示
go run structured_output.go
```

### Rust 版本

```bash
cd rust
cargo build --release

# 结构化输出演示
cargo run --release
```

---

## 核心概念

### JSON Schema

定义输出格式的标准：

```python
schema = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "姓名"
        },
        "age": {
            "type": "integer",
            "description": "年龄"
        },
        "email": {
            "type": "string",
            "description": "邮箱"
        }
    },
    "required": ["name", "age"],  # 必需字段
    "additionalProperties": False  # 禁止额外字段
}
```

### API 调用

```python
response = requests.post(
    f"{API_BASE_URL}/chat/completions",
    json={
        "model": MODEL_ID,
        "messages": [...],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "user_info",
                "schema": schema,
                "strict": True  # 关键：强制模式
            }
        }
    }
)
```

---

## 对比

### 普通 JSON vs 结构化输出

| 特性 | 普通 JSON | 结构化输出 |
|------|----------|-----------|
| 格式保证 | ❌ 可能错误 | ✅ 100% 正确 |
| Markdown | ⚠️ 可能包含 | ✅ 纯 JSON |
| 字段名 | ⚠️ 可能不一致 | ✅ 严格匹配 |
| 字段类型 | ⚠️ 可能不匹配 | ✅ 严格匹配 |
| 必需字段 | ⚠️ 可能缺失 | ✅ 保证存在 |
| 额外字段 | ⚠️ 可能出现 | ✅ 可控制 |

### 实际对比

**普通 JSON 输出：**
```json
{
  "姓名": "张三",
  "年龄": 28,
  "职业": "Python工程师"
}
```
- 字段名是中文
- 可能缺少必需字段

**结构化输出：**
```json
{
  "name": "张三",
  "age": 28,
  "position": "Python工程师",
  "email": "zhangsan@example.com"
}
```
- 字段名严格匹配 schema
- 必需字段保证存在

---

## 应用场景

### 1. 数据提取

从非结构化文本中提取结构化数据：

**输入：**
```
李明，30岁，全栈工程师，拥有5年开发经验。
联系方式：liming@example.com，电话：13800138000
技能：Python, JavaScript, React, Django
```

**输出：**
```json
{
  "name": "李明",
  "age": 30,
  "position": "全栈工程师",
  "experience_years": 5,
  "email": "liming@example.com",
  "phone": "13800138000",
  "skills": ["Python", "JavaScript", "React", "Django"]
}
```

### 2. 表单填充

将自然语言转换为标准表单：

**输入：**
```
我叫王芳，今年25岁，女性。
我住在北京市朝阳区建国路88号。
手机号是13900139000，邮箱是wangfang@example.com。
```

**输出：**
```json
{
  "personal_info": {
    "name": "王芳",
    "age": 25,
    "gender": "female"
  },
  "address": {
    "street": "建国路88号",
    "city": "北京市",
    "district": "朝阳区"
  },
  "contact": {
    "phone": "13900139000",
    "email": "wangfang@example.com"
  }
}
```

### 3. API 响应格式化

生成标准 API 响应：

**输入：**
```
查询用户ID为12345的信息
```

**输出：**
```json
{
  "status": "success",
  "code": 200,
  "message": "查询成功",
  "data": {
    "user_id": 12345,
    "username": "zhangsan",
    "email": "zhangsan@example.com",
    "is_active": true
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

---

## 技术要点

### 1. JSON Schema 设计

**基本类型：**
```python
{
    "type": "string"   # 字符串
    "type": "integer"  # 整数
    "type": "number"   # 数字（含小数）
    "type": "boolean"  # 布尔值
    "type": "array"    # 数组
    "type": "object"   # 对象
}
```

**枚举值：**
```python
{
    "type": "string",
    "enum": ["male", "female", "other"]
}
```

**嵌套对象：**
```python
{
    "type": "object",
    "properties": {
        "address": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "street": {"type": "string"}
            }
        }
    }
}
```

**数组：**
```python
{
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "price": {"type": "number"}
        }
    }
}
```

### 2. 必需字段

```python
{
    "type": "object",
    "properties": {...},
    "required": ["name", "age", "email"]  # 必需字段
}
```

### 3. 禁止额外字段

```python
{
    "type": "object",
    "properties": {...},
    "additionalProperties": False  # 禁止额外字段
}
```

---

## 最佳实践

### 1. Schema 设计

**✅ 好的设计：**
```python
{
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "用户姓名"  # 添加描述
        },
        "age": {
            "type": "integer",
            "minimum": 0,  # 添加约束
            "maximum": 150
        }
    },
    "required": ["name"]  # 只标记真正必需的字段
}
```

**❌ 差的设计：**
```python
{
    "type": "object",
    "properties": {
        "data": {"type": "string"}  # 太模糊
    },
    "required": ["data", "extra1", "extra2", ...]  # 太多必需字段
}
```

### 2. 错误处理

```python
try:
    result = json.loads(response_content)
    # 结构化输出保证格式正确
except json.JSONDecodeError:
    # 理论上不会发生
    pass
```

### 3. 类型安全

**Python + Pydantic：**
```python
from pydantic import BaseModel

class UserInfo(BaseModel):
    name: str
    age: int
    email: str

# 自动验证
user = UserInfo(**json_data)
```

---

## 常见问题

### Q: 结构化输出会增加成本吗？

A: 不会。Token 数量相同，成本相同。

### Q: 所有模型都支持吗？

A: **不是所有模型都支持 `response_format` 参数：**

**✅ 支持的模型：**
- OpenAI GPT-4/GPT-3.5 Turbo
- Anthropic Claude（不同参数）
- 部分本地模型（如果实现了 OpenAI 兼容接口）

**❌ 可能不支持：**
- 部分本地模型
- 旧版本模型

**降级方案：**
如果模型不支持，可以用 Prompt Engineering：
```python
system_prompt = f"""你必须严格按照以下 JSON Schema 返回：
{json.dumps(schema)}
要求：只返回纯 JSON，不要 markdown"""
```

### Q: 和 Prompt Engineering 的区别？

A: 
- Prompt Engineering：依赖模型"理解"，不保证格式
- 结构化输出：API 层面强制，100% 保证格式

### Q: 什么时候用结构化输出？

A: 
- ✅ 需要严格格式的场景
- ✅ 生产环境
- ✅ 需要类型安全
- ❌ 简单的文本生成
- ❌ 模型不支持时

---

## 与其他技术的关系

### vs Prompt Engineering

| 特性 | Prompt Engineering | 结构化输出 |
|------|-------------------|-----------|
| 格式保证 | ⚠️ 不保证 | ✅ 100% 保证 |
| 实现复杂度 | ⭐ 简单 | ⭐⭐ 稍复杂 |
| 适用场景 | 文本生成 | 数据提取 |

### vs Function Call

| 特性 | Function Call | 结构化输出 |
|------|--------------|-----------|
| 用途 | 调用工具 | 格式化输出 |
| 交互 | 多轮 | 单轮 |
| 适用场景 | 执行操作 | 返回数据 |

### 配合使用

```python
# Function Call 返回数据
tool_result = call_tool("search", {"query": "..."})

# 结构化输出格式化结果
formatted_result = structured_output(
    f"格式化这个结果: {tool_result}",
    schema=response_schema
)
```

---

## 实战建议

### 1. 从简单开始

先定义简单的 schema，逐步增加复杂度。

### 2. 添加描述

给每个字段添加 `description`，帮助模型理解。

### 3. 合理使用约束

- `required` - 只标记真正必需的字段
- `enum` - 限制可选值
- `minimum/maximum` - 数值范围
- `additionalProperties` - 控制额外字段

### 4. 测试验证

用真实数据测试 schema 是否合理。

---

## 总结

### 核心价值

1. **格式保证** - 100% 符合 JSON Schema
2. **类型安全** - 严格类型匹配
3. **生产可用** - 可靠性高

### 何时使用

✅ **适合：**
- 数据提取
- 表单填充
- API 响应
- 需要严格格式的场景

❌ **不适合：**
- 简单文本生成
- 创意写作
- 不需要格式的场景

### 学习建议

1. 先学 JSON Schema 基础
2. 从简单案例开始
3. 逐步增加复杂度
4. 配合 Pydantic 等工具使用

---

**记住：结构化输出是生产环境的最佳选择，特别是需要严格格式的场景。**
