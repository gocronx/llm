"""
使用 Prompt Engineering 模拟 Function Call
适用于不支持原生 Function Call 的模型
注意：这种方式不如原生支持可靠
"""

import json
from llm_client import LLMClient
from function_definitions import FUNCTION_DEFINITIONS, execute_function
from colorama import Fore, Style, init

init(autoreset=True)


def create_function_prompt(functions):
    """创建包含函数定义的 prompt"""
    
    prompt = """你是一个智能助手，可以调用以下函数来帮助用户：

可用函数列表：
"""
    
    for func in functions:
        prompt += f"\n函数名: {func['name']}\n"
        prompt += f"描述: {func['description']}\n"
        prompt += f"参数: {json.dumps(func['parameters'], ensure_ascii=False, indent=2)}\n"
    
    prompt += """
当用户的问题需要调用函数时，请严格按照以下 JSON 格式回复：

```json
{
  "action": "function_call",
  "function_name": "函数名",
  "arguments": {
    "参数名": "参数值"
  }
}
```

如果不需要调用函数，直接回答用户的问题即可。

重要：如果需要调用函数，只返回 JSON，不要添加其他文字。
"""
    
    return prompt


def parse_llm_response(response_text):
    """解析 LLM 的响应，提取函数调用"""
    
    # 尝试提取 JSON
    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        json_str = response_text[start:end].strip()
    elif "```" in response_text:
        start = response_text.find("```") + 3
        end = response_text.find("```", start)
        json_str = response_text[start:end].strip()
    else:
        json_str = response_text.strip()
    
    try:
        data = json.loads(json_str)
        if data.get("action") == "function_call":
            return {
                "is_function_call": True,
                "function_name": data.get("function_name"),
                "arguments": data.get("arguments", {})
            }
    except json.JSONDecodeError:
        pass
    
    return {
        "is_function_call": False,
        "text": response_text
    }


def run_prompt_based_function_call(user_message: str):
    """使用 Prompt Engineering 实现 Function Call"""
    
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"用户问题: {user_message}")
    print(f"{'='*70}{Style.RESET_ALL}\n")
    
    # 初始化客户端
    client = LLMClient()
    
    # 创建系统 prompt
    system_prompt = create_function_prompt(FUNCTION_DEFINITIONS)
    
    # 构建消息
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    # 第一次调用
    print(f"{Fore.YELLOW}📤 步骤1: 发送请求到 LLM{Style.RESET_ALL}")
    print("正在分析用户问题...\n")
    
    try:
        response = client.chat_completion(messages=messages, temperature=0.3)
        response_text = client.get_message_content(response)
        
        # 解析响应
        parsed = parse_llm_response(response_text)
        
        if parsed["is_function_call"]:
            # LLM 决定调用函数
            print(f"{Fore.GREEN}✓ 步骤2: LLM 决定调用函数{Style.RESET_ALL}")
            print(f"函数名: {Fore.CYAN}{parsed['function_name']}{Style.RESET_ALL}")
            print(f"参数: {Fore.CYAN}{json.dumps(parsed['arguments'], ensure_ascii=False)}{Style.RESET_ALL}\n")
            
            # 执行函数
            print(f"{Fore.YELLOW}⚙️  步骤3: 执行函数{Style.RESET_ALL}")
            function_result = execute_function(parsed['function_name'], parsed['arguments'])
            print(f"函数返回:\n{Fore.CYAN}{function_result}{Style.RESET_ALL}\n")
            
            # 第二次调用：生成最终回答
            print(f"{Fore.YELLOW}📤 步骤4: 生成最终回答{Style.RESET_ALL}\n")
            
            messages.append({"role": "assistant", "content": response_text})
            messages.append({
                "role": "user",
                "content": f"函数执行结果：{function_result}\n\n请根据这个结果，用自然语言回答我的问题。"
            })
            
            final_response = client.chat_completion(messages=messages, temperature=0.7)
            final_answer = client.get_message_content(final_response)
            
            print(f"{Fore.GREEN}✓ 步骤5: 最终回答{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{final_answer}{Style.RESET_ALL}\n")
            
        else:
            # 直接回答
            print(f"{Fore.GREEN}✓ LLM 直接回答（无需函数调用）{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{parsed['text']}{Style.RESET_ALL}\n")
    
    except Exception as e:
        print(f"{Fore.RED}❌ 错误: {str(e)}{Style.RESET_ALL}\n")


def main():
    """主函数"""
    
    print(f"\n{Fore.CYAN}{'🔧 ' * 35}")
    print("基于 Prompt 的 Function Call 模拟")
    print("适用于不支持原生 Function Call 的模型")
    print(f"{'🔧 ' * 35}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}注意：{Style.RESET_ALL}")
    print("这种方式依赖模型理解和遵循指令的能力")
    print("可能不如原生 Function Call 可靠\n")
    
    # 示例1：天气查询
    print(f"\n{Fore.MAGENTA}【示例 1】天气查询{Style.RESET_ALL}")
    run_prompt_based_function_call("深圳今天天气怎么样？")
    
    # 示例2：数学计算
    print(f"\n{Fore.MAGENTA}【示例 2】数学计算{Style.RESET_ALL}")
    run_prompt_based_function_call("帮我计算 156 除以 12")
    
    # 示例3：数据库搜索
    print(f"\n{Fore.MAGENTA}【示例 3】数据库搜索{Style.RESET_ALL}")
    run_prompt_based_function_call("搜索价格在500元以上的产品")
    
    print(f"\n{Fore.GREEN}{'='*70}")
    print("演示完成！")
    print(f"{'='*70}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}💡 对比：{Style.RESET_ALL}")
    print("• 原生 Function Call：准确、可靠、结构化")
    print("• Prompt 模拟：依赖模型能力，可能不稳定")
    print("\n推荐使用支持原生 Function Call 的模型！\n")


if __name__ == "__main__":
    main()
