"""
Function Call 格式对比
展示不同模型提供商使用的格式差异
"""

import json
from colorama import Fore, Style, init

init(autoreset=True)

print(f"\n{Fore.CYAN}{'='*70}")
print("Function Call 格式对比")
print(f"{'='*70}{Style.RESET_ALL}\n")


# ============================================================
# 格式 1: functions 格式（OpenAI 原始格式）
# ============================================================

print(f"{Fore.GREEN}【格式 1】functions 格式（OpenAI 原始格式）{Style.RESET_ALL}\n")

print("使用这个格式的模型：")
print("  • OpenAI GPT-4 / GPT-3.5")
print("  • Azure OpenAI")
print("  • DeepSeek")
print("  • 大多数兼容 OpenAI API 的模型\n")

functions_format = {
    "model": "gpt-4",
    "messages": [
        {"role": "user", "content": "北京天气怎么样？"}
    ],
    "functions": [  # ← 注意：使用 "functions" 字段
        {
            "name": "get_weather",
            "description": "获取天气信息",
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
    ],
    "function_call": "auto"  # ← 控制是否调用函数
}

print("API 请求格式：")
print(json.dumps(functions_format, ensure_ascii=False, indent=2))

print(f"\n{Fore.YELLOW}模型返回格式：{Style.RESET_ALL}")
functions_response = {
    "choices": [{
        "message": {
            "role": "assistant",
            "content": None,
            "function_call": {  # ← 返回 function_call
                "name": "get_weather",
                "arguments": '{"city": "北京"}'
            }
        }
    }]
}
print(json.dumps(functions_response, ensure_ascii=False, indent=2))


# ============================================================
# 格式 2: tools 格式（新标准）
# ============================================================

print(f"\n\n{Fore.GREEN}【格式 2】tools 格式（新标准）{Style.RESET_ALL}\n")

print("使用这个格式的模型：")
print("  • OpenAI GPT-4 Turbo（也支持）")
print("  • Anthropic Claude 3")
print("  • 智谱 GLM-4")
print("  • 通义千问")
print("  • Google Gemini\n")

tools_format = {
    "model": "gpt-4-turbo",
    "messages": [
        {"role": "user", "content": "北京天气怎么样？"}
    ],
    "tools": [  # ← 注意：使用 "tools" 字段
        {
            "type": "function",  # ← 多了一层包装
            "function": {
                "name": "get_weather",
                "description": "获取天气信息",
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
        }
    ],
    "tool_choice": "auto"  # ← 注意：字段名不同
}

print("API 请求格式：")
print(json.dumps(tools_format, ensure_ascii=False, indent=2))

print(f"\n{Fore.YELLOW}模型返回格式：{Style.RESET_ALL}")
tools_response = {
    "choices": [{
        "message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [  # ← 返回 tool_calls（数组）
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"city": "北京"}'
                    }
                }
            ]
        }
    }]
}
print(json.dumps(tools_response, ensure_ascii=False, indent=2))


# ============================================================
# 核心差异对比
# ============================================================

print(f"\n\n{Fore.CYAN}{'='*70}")
print("核心差异对比")
print(f"{'='*70}{Style.RESET_ALL}\n")

comparison = [
    {
        "项目": "请求字段名",
        "functions 格式": "functions",
        "tools 格式": "tools"
    },
    {
        "项目": "函数定义",
        "functions 格式": "直接是函数对象",
        "tools 格式": '{"type": "function", "function": {...}}'
    },
    {
        "项目": "控制字段",
        "functions 格式": "function_call",
        "tools 格式": "tool_choice"
    },
    {
        "项目": "返回字段",
        "functions 格式": "function_call (单个)",
        "tools 格式": "tool_calls (数组)"
    },
    {
        "项目": "支持并行调用",
        "functions 格式": "❌ 不支持",
        "tools 格式": "✅ 支持"
    }
]

for item in comparison:
    print(f"{Fore.YELLOW}{item['项目']}:{Style.RESET_ALL}")
    print(f"  functions 格式: {item['functions 格式']}")
    print(f"  tools 格式:     {item['tools 格式']}\n")


# ============================================================
# 函数定义部分是相同的！
# ============================================================

print(f"\n{Fore.GREEN}【重要】函数定义部分是相同的！{Style.RESET_ALL}\n")

print("无论哪种格式，函数的定义都使用 JSON Schema：\n")

function_definition = {
    "name": "get_weather",
    "description": "获取天气信息",
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

print(json.dumps(function_definition, ensure_ascii=False, indent=2))

print(f"\n{Fore.CYAN}💡 这部分在两种格式中完全一样！{Style.RESET_ALL}")
print("只是外层的包装方式不同：")
print("  • functions 格式：直接放在 functions 数组里")
print("  • tools 格式：包装在 {\"type\": \"function\", \"function\": {...}} 里\n")


# ============================================================
# 我们的项目如何处理？
# ============================================================

print(f"\n{Fore.GREEN}【我们的项目如何处理？】{Style.RESET_ALL}\n")

print("在 llm_client.py 中，我们自动处理了格式转换：\n")

print(f"{Fore.YELLOW}代码示例：{Style.RESET_ALL}")
print("""
def chat_completion(self, messages, functions=None, ...):
    params = {
        "model": self.model_id,
        "messages": messages
    }
    
    if functions:
        # 根据提供商自动选择格式
        if self.provider in ["openai", "azure", "deepseek"]:
            params["functions"] = functions        # ← functions 格式
            params["function_call"] = "auto"
        
        elif self.provider in ["zhipu", "qwen"]:
            params["tools"] = self._convert_to_tools(functions)  # ← tools 格式
            params["tool_choice"] = "auto"
    
    return self.client.chat.completions.create(**params)
""")

print(f"\n{Fore.CYAN}💡 你不需要担心格式差异！{Style.RESET_ALL}")
print("我们的代码会自动处理，你只需要：")
print("  1. 定义函数（Python 代码）")
print("  2. 写函数描述（JSON Schema）")
print("  3. 其他的交给我们的代码处理\n")


# ============================================================
# 实际建议
# ============================================================

print(f"\n{Fore.CYAN}{'='*70}")
print("实际建议")
print(f"{'='*70}{Style.RESET_ALL}\n")

print(f"{Fore.GREEN}✅ 推荐做法：{Style.RESET_ALL}\n")

print("1. 使用我们提供的 llm_client.py")
print("   • 自动处理格式差异")
print("   • 支持多种模型提供商")
print("   • 统一的接口\n")

print("2. 只关注函数定义")
print("   • 函数的 JSON Schema 定义是通用的")
print("   • 不需要关心外层包装格式\n")

print("3. 如果直接使用 OpenAI SDK")
print("   • OpenAI 的新版本同时支持两种格式")
print("   • 推荐使用 tools 格式（更强大）\n")


# ============================================================
# 总结
# ============================================================

print(f"\n{Fore.CYAN}{'='*70}")
print("总结")
print(f"{'='*70}{Style.RESET_ALL}\n")

print(f"{Fore.YELLOW}格式差异：{Style.RESET_ALL}")
print("  • 主要有两种格式：functions 和 tools")
print("  • 差异主要在外层包装，核心定义相同")
print("  • 大多数模型都支持其中一种或两种\n")

print(f"{Fore.YELLOW}你需要关心吗？{Style.RESET_ALL}")
print("  • ❌ 如果使用我们的 llm_client.py - 不需要关心")
print("  • ❌ 如果只用一个模型 - 不需要关心")
print("  • ✅ 如果要支持多个模型 - 需要了解（但我们已经处理了）\n")

print(f"{Fore.YELLOW}核心不变的是：{Style.RESET_ALL}")
print("  • 函数定义使用 JSON Schema ✓")
print("  • 包含 name, description, parameters ✓")
print("  • 这部分在所有模型中都一样 ✓\n")

print(f"{Fore.GREEN}🎯 结论：{Style.RESET_ALL}")
print("格式差异存在，但不用担心！")
print("我们的代码已经帮你处理好了。")
print("你只需要专注于定义函数和写好描述。\n")
