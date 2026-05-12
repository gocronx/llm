"""
最简单的 Function Call 完整示例
展示：定义函数 → 提供描述 → 模型判断 → 执行函数
"""

import json

print("=" * 70)
print("Function Call 完整流程示例")
print("=" * 70)

# ============================================================
# 第1步：你定义函数（实际的 Python 代码）
# ============================================================

print("\n【第1步】定义函数\n")

def get_weather(city: str) -> str:
    """获取天气 - 这是你写的实际代码"""
    weather_db = {
        "北京": "晴天，25°C",
        "上海": "多云，28°C",
        "深圳": "小雨，30°C"
    }
    return weather_db.get(city, "未知")

def send_email(to: str, subject: str) -> str:
    """发送邮件 - 这是你写的实际代码"""
    return f"邮件已发送到 {to}，主题：{subject}"

print("✓ 定义了 2 个函数：")
print("  - get_weather(city)")
print("  - send_email(to, subject)")


# ============================================================
# 第2步：准备函数描述（给模型看的"说明书"）
# ============================================================

print("\n【第2步】准备函数描述\n")

functions = [
    {
        "name": "get_weather",
        "description": "获取指定城市的天气信息",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，如：北京、上海"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_email",
        "description": "发送电子邮件给指定收件人",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "收件人邮箱地址"
                },
                "subject": {
                    "type": "string",
                    "description": "邮件主题"
                }
            },
            "required": ["to", "subject"]
        }
    }
]

print("✓ 准备了函数描述（JSON Schema）：")
for func in functions:
    print(f"  - {func['name']}: {func['description']}")


# ============================================================
# 第3步：模拟发送给模型（实际使用 API）
# ============================================================

print("\n【第3步】发送给模型\n")

user_question = "北京今天天气怎么样？"

api_request = {
    "messages": [
        {"role": "user", "content": user_question}
    ],
    "functions": functions  # ← 把所有函数描述给模型
}

print(f"用户问题: {user_question}")
print(f"发送给模型的函数数量: {len(functions)} 个")
print("  - get_weather")
print("  - send_email")


# ============================================================
# 第4步：模型判断（模拟模型的响应）
# ============================================================

print("\n【第4步】模型分析和判断\n")

print("模型的思考过程：")
print("  1. 用户问'北京天气'")
print("  2. 查看可用函数：")
print("     - get_weather: 获取天气信息 ✓ 匹配！")
print("     - send_email: 发送邮件 ✗ 不匹配")
print("  3. 决定调用 get_weather")
print("  4. 提取参数: city='北京'")

# 模拟模型返回
model_response = {
    "function_call": {
        "name": "get_weather",
        "arguments": json.dumps({"city": "北京"})
    }
}

print("\n模型返回：")
print(json.dumps(model_response, ensure_ascii=False, indent=2))


# ============================================================
# 第5步：你执行函数
# ============================================================

print("\n【第5步】执行函数\n")

# 解析模型的响应
function_name = model_response["function_call"]["name"]
arguments = json.loads(model_response["function_call"]["arguments"])

print(f"调用函数: {function_name}")
print(f"参数: {arguments}")

# 执行实际的函数
if function_name == "get_weather":
    result = get_weather(**arguments)
elif function_name == "send_email":
    result = send_email(**arguments)

print(f"\n函数返回结果: {result}")


# ============================================================
# 第6步：把结果发回模型，生成最终回答
# ============================================================

print("\n【第6步】生成最终回答\n")

print("把函数结果发回模型...")
print(f"模型看到结果: {result}")
print("\n模型生成最终回答:")
print(f"  '北京今天天气{result}'")


# ============================================================
# 对比：不同的用户问题
# ============================================================

print("\n" + "=" * 70)
print("对比：不同问题，模型的不同判断")
print("=" * 70)

test_cases = [
    {
        "question": "北京天气怎么样？",
        "expected_function": "get_weather",
        "reason": "问题是关于天气的"
    },
    {
        "question": "给 test@example.com 发邮件，主题是会议通知",
        "expected_function": "send_email",
        "reason": "问题是关于发邮件的"
    },
    {
        "question": "你好，你是谁？",
        "expected_function": None,
        "reason": "不需要调用任何函数，直接回答"
    }
]

for i, case in enumerate(test_cases, 1):
    print(f"\n示例 {i}:")
    print(f"  问题: {case['question']}")
    print(f"  模型判断: {case['expected_function'] or '不调用函数'}")
    print(f"  原因: {case['reason']}")


# ============================================================
# 总结
# ============================================================

print("\n" + "=" * 70)
print("总结")
print("=" * 70)

print("""
Function Call 的完整流程：

1. 你定义函数（Python 代码）
   ✓ 可以做任何事：调用 API、查数据库、发邮件...

2. 你准备函数描述（JSON Schema）
   ✓ 告诉模型：函数名、功能、参数

3. 把所有函数描述发给模型
   ✓ 模型可以看到所有可用的函数

4. 模型分析用户问题
   ✓ 判断是否需要调用函数
   ✓ 如果需要，选择哪个函数
   ✓ 提取函数需要的参数

5. 模型返回函数调用指令
   ✓ 不是执行，只是"建议"

6. 你的代码执行函数
   ✓ 实际的业务逻辑由你控制

7. 把结果发回模型
   ✓ 模型生成最终的自然语言回答

关键点：
• 函数是你定义的 ✓
• 描述是你写的 ✓
• 判断是模型做的 ✓
• 执行是你做的 ✓
""")

print("\n现在你可以在 function_definitions.py 中添加自己的函数了！")
