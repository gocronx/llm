"""
使用真实 LLM API 的 Function Call 示例
支持多种模型提供商（OpenAI、智谱、通义千问、DeepSeek 等）
配置方式：在 .env 文件中设置 API_KEY、API_BASE_URL、MODEL_ID
"""

import json
from colorama import Fore, Style, init
from llm_client import LLMClient
from function_definitions import FUNCTION_DEFINITIONS, execute_function

# 初始化 colorama（用于彩色输出）
init(autoreset=True)


def print_section(title: str, color=Fore.CYAN):
    """打印分节标题"""
    print(f"\n{color}{'='*70}")
    print(f"{title}")
    print(f"{'='*70}{Style.RESET_ALL}\n")


def print_step(step: str, content: str, color=Fore.GREEN):
    """打印步骤信息"""
    print(f"{color}{step}{Style.RESET_ALL}")
    print(f"{content}\n")


def run_conversation(client: LLMClient, user_message: str):
    """
    运行一个完整的对话，包含 function calling
    
    Args:
        client: LLM 客户端
        user_message: 用户输入的消息
    """
    print_section(f"用户问题: {user_message}", Fore.CYAN)
    
    # 准备消息
    messages = [{"role": "user", "content": user_message}]
    
    # 第一次调用：让 LLM 决定是否需要调用函数
    print_step("📤 步骤1: 发送请求到 LLM", "正在分析用户问题...", Fore.YELLOW)
    
    try:
        response = client.chat_completion(
            messages=messages,
            functions=FUNCTION_DEFINITIONS,
            function_call="auto"
        )
    except Exception as e:
        print(f"{Fore.RED}❌ API 调用失败: {str(e)}{Style.RESET_ALL}")
        return None
    
    # 检查是否需要调用函数
    function_call = client.extract_function_call(response)
    
    if function_call:
        print_step(
            "✓ 步骤2: LLM 决定调用函数",
            f"函数名: {Fore.CYAN}{function_call['name']}{Style.RESET_ALL}\n"
            f"参数: {Fore.CYAN}{function_call['arguments']}{Style.RESET_ALL}",
            Fore.GREEN
        )
        
        # 解析参数
        function_name = function_call["name"]
        function_args = json.loads(function_call["arguments"])
        
        # 执行函数
        print_step("⚙️  步骤3: 执行函数", "正在调用本地函数...", Fore.YELLOW)
        function_response = execute_function(function_name, function_args)
        print(f"函数返回结果:\n{Fore.CYAN}{function_response}{Style.RESET_ALL}\n")
        
        # 将函数调用和结果添加到消息历史
        response_message = client.get_response_message(response)
        messages.append(response_message)
        messages.append({
            "role": "function",
            "name": function_name,
            "content": function_response
        })
        
        # 第二次调用：让 LLM 基于函数结果生成回答
        print_step("📤 步骤4: 将函数结果发送回 LLM", "正在生成最终回答...", Fore.YELLOW)
        
        try:
            second_response = client.chat_completion(messages=messages)
            final_answer = client.get_message_content(second_response)
            
            print_step(
                "✓ 步骤5: 最终回答",
                f"{Fore.GREEN}{final_answer}{Style.RESET_ALL}",
                Fore.GREEN
            )
            
            return final_answer
        except Exception as e:
            print(f"{Fore.RED}❌ 第二次 API 调用失败: {str(e)}{Style.RESET_ALL}")
            return None
    
    else:
        # 不需要调用函数，直接返回回答
        answer = client.get_message_content(response)
        print_step(
            "✓ LLM 直接回答（无需函数调用）",
            f"{Fore.GREEN}{answer}{Style.RESET_ALL}",
            Fore.GREEN
        )
        return answer


def run_multiple_function_calls(client: LLMClient, user_message: str):
    """
    演示可能需要多次函数调用的场景
    
    Args:
        client: LLM 客户端
        user_message: 用户输入的消息
    """
    print_section(f"复杂问题: {user_message}", Fore.CYAN)
    
    messages = [{"role": "user", "content": user_message}]
    
    max_iterations = 5  # 防止无限循环
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        print(f"\n{Fore.YELLOW}--- 第 {iteration} 轮交互 ---{Style.RESET_ALL}\n")
        
        try:
            response = client.chat_completion(
                messages=messages,
                functions=FUNCTION_DEFINITIONS,
                function_call="auto"
            )
        except Exception as e:
            print(f"{Fore.RED}❌ API 调用失败: {str(e)}{Style.RESET_ALL}")
            return None
        
        # 检查是否需要调用函数
        function_call = client.extract_function_call(response)
        
        # 如果没有函数调用，说明对话结束
        if not function_call:
            final_answer = client.get_message_content(response)
            print_step(
                "✓ 最终回答",
                f"{Fore.GREEN}{final_answer}{Style.RESET_ALL}",
                Fore.GREEN
            )
            return final_answer
        
        # 有函数调用，执行它
        function_name = function_call["name"]
        function_args = json.loads(function_call["arguments"])
        
        print(f"调用函数: {Fore.CYAN}{function_name}{Style.RESET_ALL}")
        print(f"参数: {Fore.CYAN}{json.dumps(function_args, ensure_ascii=False)}{Style.RESET_ALL}")
        
        function_response = execute_function(function_name, function_args)
        print(f"结果: {Fore.CYAN}{function_response}{Style.RESET_ALL}\n")
        
        # 更新消息历史
        response_message = client.get_response_message(response)
        messages.append(response_message)
        messages.append({
            "role": "function",
            "name": function_name,
            "content": function_response
        })
    
    print(f"{Fore.RED}⚠️  达到最大迭代次数{Style.RESET_ALL}")
    return None


def main():
    """主函数"""
    print(f"\n{Fore.CYAN}{'🚀 ' * 35}")
    print("LLM Function Call 真实调用示例")
    print(f"{'🚀 ' * 35}{Style.RESET_ALL}\n")
    
    # 初始化 LLM 客户端
    try:
        client = LLMClient()
    except Exception as e:
        print(f"\n{Fore.RED}❌ 初始化失败: {str(e)}{Style.RESET_ALL}\n")
        print("请检查 .env 文件配置:")
        print("  1. 复制 .env.example 为 .env")
        print("  2. 填入你的 API_KEY")
        print("  3. 设置正确的 API_BASE_URL 和 MODEL_ID")
        print("\n示例配置:")
        print("  API_KEY=sk-xxx")
        print("  API_BASE_URL=https://api.openai.com/v1")
        print("  MODEL_ID=gpt-4-turbo-preview\n")
        return
    
    # 示例1：简单的函数调用
    print(f"\n\n{Fore.MAGENTA}【示例 1】天气查询{Style.RESET_ALL}")
    run_conversation(client, "深圳今天天气怎么样？")
    
    # 示例2：计算
    print(f"\n\n{Fore.MAGENTA}【示例 2】数学计算{Style.RESET_ALL}")
    run_conversation(client, "帮我计算 156 除以 12 等于多少")
    
    # 示例3：数据库搜索
    print(f"\n\n{Fore.MAGENTA}【示例 3】数据库搜索{Style.RESET_ALL}")
    run_conversation(client, "搜索一下价格在500元以上的产品")
    
    # 示例4：可能需要多次函数调用
    print(f"\n\n{Fore.MAGENTA}【示例 4】复杂查询（多次函数调用）{Style.RESET_ALL}")
    run_multiple_function_calls(client, "比较一下北京和上海今天的天气，哪个城市温度更高？")
    
    print(f"\n{Fore.GREEN}{'='*70}")
    print("演示完成！")
    print(f"{'='*70}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}💡 提示:{Style.RESET_ALL}")
    print("  - 你可以修改 .env 文件切换不同的模型")
    print("  - 支持 OpenAI、智谱、通义千问、DeepSeek 等")
    print("  - 可以在 function_definitions.py 中添加自己的函数\n")


if __name__ == "__main__":
    main()
