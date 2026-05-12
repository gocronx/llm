"""
理解 Function Call：谁定义函数？谁执行函数？
"""

import json
from colorama import Fore, Style, init

init(autoreset=True)


print(f"\n{Fore.CYAN}{'='*70}")
print("Function Call 角色分工详解")
print(f"{'='*70}{Style.RESET_ALL}\n")


# ============================================================
# 第一部分：开发者（你）定义函数
# ============================================================

print(f"{Fore.GREEN}【第一步】开发者定义函数{Style.RESET_ALL}\n")

print("这是你写的 Python 代码：\n")
print(f"{Fore.YELLOW}# 1. 实现实际的函数逻辑")
print("""def get_weather(city: str) -> str:
    '''获取天气信息 - 这是你自己写的代码'''
    
    # 这里可以调用真实的天气 API
    # 或者从数据库查询
    # 或者任何你想做的事情
    
    weather_data = {
        "北京": {"condition": "晴天", "temp": "25°C"},
        "上海": {"condition": "多云", "temp": "28°C"}
    }
    
    result = weather_data.get(city, {"condition": "未知", "temp": "N/A"})
    return json.dumps(result, ensure_ascii=False)
""")

print(f"\n{Fore.YELLOW}# 2. 定义函数的 JSON Schema（告诉 LLM）")
print("""function_definition = {
    "name": "get_weather",
    "description": "获取指定城市的天气信息",  # 告诉 LLM 这个函数是干什么的
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "城市名称，例如：北京、上海"  # 告诉 LLM 参数的含义
            }
        },
        "required": ["city"]
    }
}
""")

print(f"{Style.RESET_ALL}\n")
print(f"{Fore.CYAN}💡 关键点：{Style.RESET_ALL}")
print("• 函数的实现（Python 代码）是你写的")
print("• 函数的描述（JSON Schema）也是你写的")
print("• LLM 不知道你的函数内部做了什么，它只看描述\n")


# ============================================================
# 第二部分：LLM 的工作
# ============================================================

print(f"\n{Fore.GREEN}【第二步】LLM 分析和决策{Style.RESET_ALL}\n")

print("用户问题：'北京今天天气怎么样？'\n")

print(f"{Fore.YELLOW}LLM 的思考过程：{Style.RESET_ALL}")
print("""
1. 分析用户问题：用户想知道北京的天气
2. 查看可用函数列表：
   - 发现有一个 get_weather 函数
   - 描述说：'获取指定城市的天气信息'
   - 参数需要：city（城市名称）
3. 决策：这个问题需要调用 get_weather 函数
4. 提取参数：city = "北京"
5. 返回函数调用指令（不是执行函数！）
""")

print(f"{Fore.YELLOW}LLM 返回的内容：{Style.RESET_ALL}")
llm_response = {
    "function_call": {
        "name": "get_weather",
        "arguments": '{"city": "北京"}'
    }
}
print(json.dumps(llm_response, ensure_ascii=False, indent=2))

print(f"\n{Fore.CYAN}💡 关键点：{Style.RESET_ALL}")
print("• LLM 只是返回'应该调用哪个函数，用什么参数'")
print("• LLM 不会真正执行你的 Python 函数")
print("• LLM 不知道函数内部的实现细节\n")


# ============================================================
# 第三部分：开发者执行函数
# ============================================================

print(f"\n{Fore.GREEN}【第三步】开发者执行函数{Style.RESET_ALL}\n")

print(f"{Fore.YELLOW}你的代码接收到 LLM 的响应后：{Style.RESET_ALL}\n")

print("""# 1. 解析 LLM 返回的函数调用信息
function_name = "get_weather"
arguments = {"city": "北京"}

# 2. 执行你自己定义的函数
result = get_weather(**arguments)

# 3. 得到结果
print(result)  # {"condition": "晴天", "temp": "25°C"}
""")

print(f"{Fore.CYAN}💡 关键点：{Style.RESET_ALL}")
print("• 函数的执行是你的代码完成的")
print("• LLM 只是告诉你'该调用哪个函数'")
print("• 函数可以做任何事：调用 API、查数据库、发邮件等\n")


# ============================================================
# 第四部分：完整流程
# ============================================================

print(f"\n{Fore.GREEN}【完整流程图】{Style.RESET_ALL}\n")

print("""
用户: "北京天气怎么样？"
  │
  ▼
┌─────────────────────────────────────┐
│ 你的代码：发送请求到 LLM            │
│ - 用户问题                          │
│ - 可用函数列表（你定义的）          │
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ LLM：分析和决策                     │
│ - 理解问题                          │
│ - 查看函数列表                      │
│ - 决定调用 get_weather              │
│ - 提取参数 {"city": "北京"}         │
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ LLM 返回：                          │
│ {                                   │
│   "function_call": {                │
│     "name": "get_weather",          │
│     "arguments": "{\\"city\\": \\"北京\\"}" │
│   }                                 │
│ }                                   │
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ 你的代码：执行函数                  │
│ result = get_weather(city="北京")   │
│ # 这是你的 Python 函数              │
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ 函数返回结果：                      │
│ {"condition": "晴天", "temp": "25°C"}│
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ 你的代码：将结果发回 LLM            │
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ LLM：生成最终回答                   │
│ "北京今天天气晴朗，温度25摄氏度"    │
└─────────────────────────────────────┘
  │
  ▼
用户看到最终回答
""")


# ============================================================
# 第五部分：你可以定义任何函数
# ============================================================

print(f"\n{Fore.GREEN}【你可以定义任何函数】{Style.RESET_ALL}\n")

print(f"{Fore.YELLOW}示例 1：发送邮件{Style.RESET_ALL}")
print("""
def send_email(to: str, subject: str, body: str):
    '''你自己实现的发邮件功能'''
    import smtplib
    # 你的邮件发送逻辑
    return "邮件已发送"

# 告诉 LLM 这个函数
function_def = {
    "name": "send_email",
    "description": "发送电子邮件",
    "parameters": {...}
}
""")

print(f"\n{Fore.YELLOW}示例 2：查询数据库{Style.RESET_ALL}")
print("""
def query_database(sql: str):
    '''你自己实现的数据库查询'''
    import sqlite3
    # 你的数据库查询逻辑
    return results

# 告诉 LLM 这个函数
function_def = {
    "name": "query_database",
    "description": "查询数据库",
    "parameters": {...}
}
""")

print(f"\n{Fore.YELLOW}示例 3：控制智能家居{Style.RESET_ALL}")
print("""
def control_light(room: str, action: str):
    '''你自己实现的智能家居控制'''
    # 调用智能家居 API
    return "灯已打开"

# 告诉 LLM 这个函数
function_def = {
    "name": "control_light",
    "description": "控制房间灯光",
    "parameters": {...}
}
""")

print(f"\n{Fore.CYAN}💡 总结：{Style.RESET_ALL}")
print("• 函数是你自己定义的，想做什么都可以")
print("• LLM 只负责'决定何时调用哪个函数'")
print("• 函数的实际执行由你的代码完成")
print("• 这就是为什么叫 'Function Call' 而不是 'Function Execution'\n")


# ============================================================
# 第六部分：对比
# ============================================================

print(f"\n{Fore.GREEN}【对比：有 Function Call vs 没有 Function Call】{Style.RESET_ALL}\n")

print(f"{Fore.RED}❌ 没有 Function Call：{Style.RESET_ALL}")
print("""
用户: "北京天气怎么样？"
LLM: "抱歉，我无法获取实时天气信息。我的知识截止到2023年..."
     （LLM 无法访问外部数据）
""")

print(f"{Fore.GREEN}✅ 有 Function Call：{Style.RESET_ALL}")
print("""
用户: "北京天气怎么样？"
LLM: 决定调用 get_weather(city="北京")
你的代码: 执行函数，调用天气 API
LLM: "北京今天天气晴朗，温度25摄氏度"
     （LLM 可以通过你的函数获取实时数据）
""")


print(f"\n{Fore.CYAN}{'='*70}")
print("总结")
print(f"{'='*70}{Style.RESET_ALL}\n")

print(f"{Fore.YELLOW}Function Call 的本质：{Style.RESET_ALL}")
print("""
1. 你定义函数（Python 代码 + JSON Schema）
2. LLM 决定何时调用（基于用户问题和函数描述）
3. 你的代码执行函数（实际的业务逻辑）
4. LLM 生成回答（基于函数结果）

这是一个协作过程：
• LLM 负责理解和决策
• 你负责定义和执行
""")

print(f"\n{Fore.GREEN}🎯 现在你可以：{Style.RESET_ALL}")
print("1. 在 function_definitions.py 中添加任何你想要的函数")
print("2. 函数可以做任何事：调用 API、操作数据库、控制硬件等")
print("3. LLM 会智能地决定何时调用你的函数")
print("4. 用户得到准确、实时的信息\n")
