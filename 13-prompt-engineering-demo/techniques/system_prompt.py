"""
System Prompt 技术演示
定义 AI 的角色、行为和限制
"""

import os
import requests
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """调用 LLM"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL_ID,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return f"❌ API 错误: {response.status_code}"
    except Exception as e:
        return f"❌ 调用失败: {e}"


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{title}")
    print(f"{'='*60}{Style.RESET_ALL}\n")


def main():
    print_section("System Prompt 技术演示")
    
    user_query = "审查这段代码: def login(user, pwd): return user == 'admin' and pwd == '123'"
    
    # 示例 1: 无 System Prompt
    print(f"{Fore.GREEN}示例 1: 无 System Prompt{Style.RESET_ALL}\n")
    print(f"{Fore.YELLOW}System:{Style.RESET_ALL} (无)")
    print(f"{Fore.YELLOW}User:{Style.RESET_ALL} {user_query}\n")
    
    response = call_llm("", user_query)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 示例 2: 简单 System Prompt
    print(f"{Fore.GREEN}示例 2: 简单 System Prompt{Style.RESET_ALL}\n")
    system_simple = "你是一个代码审查助手。"
    print(f"{Fore.YELLOW}System:{Style.RESET_ALL} {system_simple}")
    print(f"{Fore.YELLOW}User:{Style.RESET_ALL} {user_query}\n")
    
    response = call_llm(system_simple, user_query)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 示例 3: 详细 System Prompt
    print(f"{Fore.GREEN}示例 3: 详细 System Prompt（推荐）{Style.RESET_ALL}\n")
    system_detailed = """你是资深 Python 安全工程师，专注代码安全审查。

你的职责:
1. 识别安全漏洞（SQL注入、XSS、硬编码密码等）
2. 评估代码质量和性能
3. 提供具体的改进建议

你的风格:
- 专业、客观、建设性
- 先指出严重问题，再提优化建议
- 给出具体的修改方案

你不应该:
- 过度批评或使用负面语言
- 给出模糊的建议
- 忽略安全问题
"""
    print(f"{Fore.YELLOW}System:{Style.RESET_ALL}")
    print(system_detailed)
    print(f"\n{Fore.YELLOW}User:{Style.RESET_ALL} {user_query}\n")
    
    response = call_llm(system_detailed, user_query)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 总结
    print_section("System Prompt 设计要点")
    
    print(f"{Fore.GREEN}✓ 好的 System Prompt 包含:{Style.RESET_ALL}\n")
    print("1. 角色定义: 你是谁？（专家、助手、工程师）")
    print("2. 职责范围: 你要做什么？（具体任务）")
    print("3. 行为风格: 你怎么做？（专业、友好、严谨）")
    print("4. 限制条件: 你不做什么？（避免的行为）\n")
    
    print(f"{Fore.YELLOW}对比效果:{Style.RESET_ALL}\n")
    print("无 System Prompt:")
    print("  → 回答通用，缺乏专业性\n")
    
    print("简单 System Prompt:")
    print("  → 有一定方向，但不够具体\n")
    
    print("详细 System Prompt:")
    print("  → 专业、结构化、针对性强")
    print("  → 质量提升 30-50%\n")
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}记住: System Prompt 是 AI 的「人设」{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
