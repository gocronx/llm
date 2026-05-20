# LLM Function Call 深度教程

## 目录
1. [什么是 Function Call](#什么是-function-call)
2. [为什么需要 Function Call](#为什么需要-function-call)
3. [工作原理详解](#工作原理详解)
4. [函数定义规范](#函数定义规范)
5. [实战技巧](#实战技巧)
6. [常见问题](#常见问题)

---

## 什么是 Function Call

Function Call（函数调用）是 LLM 的一项能力，允许模型在对话过程中调用外部函数来获取信息或执行操作。

### 核心概念

```
用户问题 → LLM 分析 → 决定调用函数 → 执行函数 → LLM 生成回答
```

**关键点：**
- LLM 本身不执行函数，只是返回"应该调用哪个函数，用什么参数"
- 实际的函数执行由我们的代码完成
- 函数结果返回给 LLM 后，LLM 生成自然语言回答

---

## 为什么需要 Function Call

### 问题场景

LLM 的局限性：
1. **知识截止日期** - 无法获取实时信息（天气、股票、新闻）
2. **无法执行操作** - 不能发送邮件、操作数据库、调用 API
3. **计算能力有限** - 复杂数学计算可能出错
4. **无法访问私有数据** - 不知道你的订单、用户信息等

### Function Call 的解决方案

通过 Function Call，LLM 可以：
- ✅ 调用天气 API 获取实时天气
- ✅ 查询数据库获取用户订单
- ✅ 使用计算器进行精确计算
- ✅ 发送邮件、创建日程等操作

---

## 工作原理详解

### 完整流程图

```
┌─────────────┐
│  用户输入    │  "北京今天天气怎么样？"
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  步骤1: 构建请求                          │
│  ─────────────────────────────────────  │
│  {                                      │
│    "messages": [                        │
│      {"role": "user",                   │
│       "content": "北京今天天气怎么样？"}  │
│    ],                                   │
│    "functions": [                       │
│      {                                  │
│        "name": "get_weather",           │
│        "description": "获取天气信息",    │
│        "parameters": {...}              │
│      }                                  │
│    ]                                    │
│  }                                      │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  步骤2: LLM 分析                         │
│  ─────────────────────────────────────  │
│  • 理解用户意图：查询天气               │
│  • 检查可用函数：发现 get_weather       │
│  • 提取参数：城市="北京"                │
│  • 决策：需要调用函数                   │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  步骤3: LLM 返回函数调用指令             │
│  ─────────────────────────────────────  │
│  {                                      │
│    "function_call": {                   │
│      "name": "get_weather",             │
│      "arguments": "{\"city\": \"北京\"}" │
│    }                                    │
│  }                                      │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  步骤4: 我们的代码执行函数               │
│  ─────────────────────────────────────  │
│  function_name = "get_weather"          │
│  arguments = {"city": "北京"}           │
│  result = get_weather(**arguments)      │
│  # 返回: {"condition": "晴天",          │
│  #        "temperature": "25°C"}        │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  步骤5: 将结果返回给 LLM                 │
│  ─────────────────────────────────────  │
│  {                                      │
│    "role": "function",                  │
│    "name": "get_weather",               │
│    "content": "{\"condition\": \"晴天\",│
│                \"temperature\": \"25°C\"}"│
│  }                                      │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  步骤6: LLM 生成最终回答                 │
│  ─────────────────────────────────────  │
│  "北京今天天气晴朗，温度25摄氏度。"      │
└─────────────────────────────────────────┘
```

### 代码实现示例

```python
# 1. 定义函数
def get_weather(city: str) -> str:
    # 实际调用天气 API
    return json.dumps({"condition": "晴天", "temp": "25°C"})

# 2. 定义函数的 JSON Schema
function_definition = {
    "name": "get_weather",
    "description": "获取指定城市的天气信息",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "城市名称"
            }
        },
        "required": ["city"]
    }
}

# 3. 调用 LLM
response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "北京天气怎么样？"}],
    functions=[function_definition]
)

# 4. 检查是否需要调用函数
if response.choices[0].message.get("function_call"):
    function_call = response.choices[0].message.function_call
    
    # 5. 执行函数
    function_name = function_call.name
    function_args = json.loads(function_call.arguments)
    function_result = get_weather(**function_args)
    
    # 6. 将结果返回给 LLM
    second_response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": "北京天气怎么样？"},
            response.choices[0].message,
            {"role": "function", "name": function_name, "content": function_result}
        ]
    )
    
    print(second_response.choices[0].message.content)
```

---

## 函数定义规范

### JSON Schema 格式

函数定义使用 JSON Schema 标准，包含三个核心部分：

```python
{
    "name": "函数名",           # 必需：函数的唯一标识符
    "description": "函数描述",   # 必需：告诉 LLM 这个函数做什么
    "parameters": {             # 必需：参数定义
        "type": "object",
        "properties": {
            "参数名": {
                "type": "类型",
                "description": "参数描述"
            }
        },
        "required": ["必需参数列表"]
    }
}
```

### 最佳实践

#### 1. 清晰的函数名

```python
# ✅ 好的命名
"get_weather"
"send_email"
"search_products"

# ❌ 不好的命名
"func1"
"do_something"
"api_call"
```

#### 2. 详细的描述

```python
# ✅ 好的描述
"description": "获取指定城市的实时天气信息，包括温度、湿度和天气状况"

# ❌ 不好的描述
"description": "天气"
```

#### 3. 明确的参数说明

```python
# ✅ 好的参数定义
"city": {
    "type": "string",
    "description": "城市名称，例如：北京、上海、深圳",
    "enum": ["北京", "上海", "深圳", "成都"]  # 可选：限制取值范围
}

# ❌ 不好的参数定义
"city": {
    "type": "string"
}
```

#### 4. 使用枚举限制选项

```python
"unit": {
    "type": "string",
    "enum": ["celsius", "fahrenheit"],
    "description": "温度单位：celsius(摄氏度) 或 fahrenheit(华氏度)"
}
```

### 完整示例

```python
{
    "name": "book_flight",
    "description": "预订航班，需要提供出发地、目的地、日期和乘客信息",
    "parameters": {
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "出发城市或机场代码，例如：北京、PEK"
            },
            "destination": {
                "type": "string",
                "description": "目的地城市或机场代码，例如：上海、SHA"
            },
            "date": {
                "type": "string",
                "description": "出发日期，格式：YYYY-MM-DD"
            },
            "passengers": {
                "type": "integer",
                "description": "乘客数量",
                "minimum": 1,
                "maximum": 9
            },
            "class": {
                "type": "string",
                "enum": ["economy", "business", "first"],
                "description": "舱位等级：economy(经济舱)、business(商务舱)、first(头等舱)"
            }
        },
        "required": ["origin", "destination", "date", "passengers"]
    }
}
```

---

## 实战技巧

### 1. 处理多个函数

LLM 可以从多个函数中选择最合适的：

```python
functions = [
    get_weather_definition,
    send_email_definition,
    search_database_definition
]

# LLM 会根据用户问题自动选择
```

### 2. 函数链式调用

有时需要多次调用函数：

```python
# 用户: "比较北京和上海的天气"
# 
# 第1次调用: get_weather(city="北京")
# 第2次调用: get_weather(city="上海")
# 最后: LLM 比较两个结果并回答
```

### 3. 错误处理

```python
def execute_function(name, args):
    try:
        result = available_functions[name](**args)
        return json.dumps({"success": True, "data": result})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
```

### 4. 参数验证

```python
def get_weather(city: str, unit: str = "celsius"):
    # 验证参数
    if unit not in ["celsius", "fahrenheit"]:
        return json.dumps({"error": "Invalid unit"})
    
    # 执行逻辑
    ...
```

### 5. 控制函数调用

```python
# 强制调用特定函数
function_call={"name": "get_weather"}

# 禁止调用函数
function_call="none"

# 自动决定（默认）
function_call="auto"
```

---

## 常见问题

### Q1: LLM 会真正执行函数吗？

**A:** 不会。LLM 只是返回"应该调用哪个函数，用什么参数"的指令。实际执行由你的代码完成。

### Q2: 函数必须返回 JSON 吗？

**A:** 函数必须返回字符串。通常使用 JSON 格式，因为它结构化且易于 LLM 理解。

### Q3: 如何让 LLM 更准确地选择函数？

**A:** 
- 写清晰的函数描述
- 提供详细的参数说明
- 使用示例值
- 限制参数的取值范围（enum）

### Q4: 可以调用多少个函数？

**A:** 理论上没有限制，但要注意：
- 函数定义会占用 token
- 太多函数可能让 LLM 困惑
- 建议：每次请求 5-10 个相关函数

### Q5: Function Call 的成本？

**A:** 
- 函数定义会计入输入 token
- 每次函数调用需要额外的 API 请求
- 建议：优化函数定义的长度

### Q6: 如何调试？

**A:**
```python
# 打印 LLM 的决策
print(f"LLM 选择: {response.function_call.name}")
print(f"参数: {response.function_call.arguments}")

# 打印函数结果
print(f"函数返回: {function_result}")
```

### Q7: 安全性考虑？

**A:**
- ⚠️ 验证 LLM 返回的参数
- ⚠️ 限制函数的权限
- ⚠️ 不要让 LLM 直接执行危险操作（删除数据、转账等）
- ✅ 敏感操作需要人工确认

---

## 进阶主题

### 1. 流式响应

```python
# 支持流式输出的 function call
for chunk in openai.ChatCompletion.create(
    model="gpt-4",
    messages=messages,
    functions=functions,
    stream=True
):
    # 处理流式数据
    ...
```

### 2. 并行函数调用

某些模型支持一次返回多个函数调用：

```python
# GPT-4 可能返回
{
    "function_calls": [
        {"name": "get_weather", "arguments": {...}},
        {"name": "get_weather", "arguments": {...}}
    ]
}
```

### 3. 与 Agent 结合

Function Call 是构建 AI Agent 的基础：

```
Agent = LLM + Function Call + 记忆 + 规划
```

---

## 总结

Function Call 的核心价值：
1. ✅ 让 LLM 能够获取实时信息
2. ✅ 让 LLM 能够执行实际操作
3. ✅ 让 LLM 能够访问私有数据
4. ✅ 提高回答的准确性和可靠性

关键要点：
- LLM 不执行函数，只返回调用指令
- 函数定义的质量决定 LLM 的选择准确性
- 需要多轮交互才能完成完整流程
- 注意安全性和参数验证

---

## 参考资源

- [OpenAI Function Calling 官方文档](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic Claude Tools](https://docs.anthropic.com/claude/docs/tool-use)
- [JSON Schema 规范](https://json-schema.org/)
