"""
Prompt Engineering 交互式工具
快速测试和优化你的 Prompt
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


def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
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
                "temperature": temperature,
                "max_tokens": 1000
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
    print_section("Prompt Engineering Playground")
    
    print(f"{Fore.YELLOW}💡 提示：{Style.RESET_ALL}")
    print("  - 输入 'quit' 退出")
    print("  - 输入 'clear' 清空")
    print("  - 输入 'examples' 查看示例\n")
    
    system_prompt = ""
    
    while True:
        try:
            # 输入 System Prompt
            print(f"{Fore.GREEN}📝 System Prompt (可选，直接回车跳过):{Style.RESET_ALL}")
            sys_input = input("> ").strip()
            
            if sys_input.lower() == 'quit':
                break
            elif sys_input.lower() == 'clear':
                system_prompt = ""
                print(f"{Fore.YELLOW}✓ 已清空 System Prompt{Style.RESET_ALL}\n")
                continue
            elif sys_input.lower() == 'examples':
                show_examples()
                continue
            
            if sys_input:
                system_prompt = sys_input
            
            # 输入 User Prompt
            print(f"\n{Fore.GREEN}💬 User Prompt:{Style.RESET_ALL}")
            user_prompt = input("> ").strip()
            
            if not user_prompt:
                continue
            
            if user_prompt.lower() == 'quit':
                break
            
            # 显示使用的 Prompt
            print_section("使用的 Prompt")
            if system_prompt:
                print(f"{Fore.YELLOW}System:{Style.RESET_ALL}")
                print(f"  {system_prompt}\n")
            print(f"{Fore.YELLOW}User:{Style.RESET_ALL}")
            print(f"  {user_prompt}\n")
            
            # 调用 LLM
            print(f"{Fore.CYAN}🤖 正在生成回答...{Style.RESET_ALL}\n")
            response = call_llm(system_prompt, user_prompt)
            
            # 显示结果
            print_section("AI 回答")
            print(response)
            
            print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
            
        except KeyboardInterrupt:
            print(f"\n\n{Fore.CYAN}再见！{Style.RESET_ALL}")
            break
        except Exception as e:
            print(f"{Fore.RED}错误: {e}{Style.RESET_ALL}\n")


def show_examples():
    """显示示例 Prompt"""
    print_section("Prompt 示例")
    
    examples = [
        {
            "name": "代码审查",
            "system": "你是资深 Python 工程师。审查代码并指出问题和改进建议。",
            "user": "审查这段代码:\ndef login(user, pwd):\n    if user == 'admin' and pwd == '123':\n        return True"
        },
        {
            "name": "数据提取",
            "system": "从文本中提取结构化信息，输出 JSON 格式。",
            "user": "提取信息: 张三，28岁，Python工程师，邮箱 zhangsan@example.com"
        },
        {
            "name": "翻译",
            "system": "你是专业翻译，将中文翻译成地道的英文。",
            "user": "翻译: 这个功能很实用"
        }
    ]
    
    for i, ex in enumerate(examples, 1):
        print(f"{Fore.GREEN}{i}. {ex['name']}{Style.RESET_ALL}")
        print(f"   System: {ex['system']}")
        print(f"   User: {ex['user']}\n")


if __name__ == "__main__":
    main()
