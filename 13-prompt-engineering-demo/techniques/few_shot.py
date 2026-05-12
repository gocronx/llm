"""
Few-shot Learning 技术演示
通过示例引导输出格式
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
                "max_tokens": 300
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
    print_section("Few-shot Learning 技术演示")
    
    text = "王五，35岁，高级Go工程师，邮箱 wangwu@tech.com，擅长微服务和Kubernetes"
    
    # 示例 1: Zero-shot（无示例）
    print(f"{Fore.GREEN}示例 1: Zero-shot（无示例）{Style.RESET_ALL}\n")
    prompt_zero = f"从文本中提取姓名、年龄、职位、邮箱、技能，输出 JSON:\n{text}"
    print(f"{Fore.YELLOW}Prompt:{Style.RESET_ALL}")
    print(prompt_zero)
    print()
    
    response = call_llm("", prompt_zero)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 示例 2: One-shot（1个示例）
    print(f"{Fore.GREEN}示例 2: One-shot（1个示例）{Style.RESET_ALL}\n")
    prompt_one = f"""从文本中提取信息，输出 JSON。

示例:
输入: "张三，28岁，Python工程师，邮箱 zhangsan@example.com，擅长 Django"
输出: {{"name": "张三", "age": 28, "position": "Python工程师", "email": "zhangsan@example.com", "skills": ["Django"]}}

现在处理:
输入: {text}
输出:"""
    print(f"{Fore.YELLOW}Prompt:{Style.RESET_ALL}")
    print(prompt_one)
    print()
    
    response = call_llm("", prompt_one)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 示例 3: Few-shot（多个示例）
    print(f"{Fore.GREEN}示例 3: Few-shot（多个示例，推荐）{Style.RESET_ALL}\n")
    prompt_few = f"""从文本中提取信息，输出 JSON。

示例1:
输入: "张三，28岁，Python工程师，邮箱 zhangsan@example.com，擅长 Django"
输出: {{"name": "张三", "age": 28, "position": "Python工程师", "email": "zhangsan@example.com", "skills": ["Django"]}}

示例2:
输入: "李四，30岁，Java开发，邮箱 lisi@company.com，擅长 Spring 和 MyBatis"
输出: {{"name": "李四", "age": 30, "position": "Java开发", "email": "lisi@company.com", "skills": ["Spring", "MyBatis"]}}

示例3:
输入: "赵六，26岁，前端工程师，邮箱 zhaoliu@startup.com，擅长 React"
输出: {{"name": "赵六", "age": 26, "position": "前端工程师", "email": "zhaoliu@startup.com", "skills": ["React"]}}

现在处理:
输入: {text}
输出:"""
    print(f"{Fore.YELLOW}Prompt:{Style.RESET_ALL}")
    print(prompt_few[:200] + "...")
    print()
    
    response = call_llm("", prompt_few)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 总结
    print_section("Few-shot Learning 要点")
    
    print(f"{Fore.GREEN}✓ 为什么需要 Few-shot?{Style.RESET_ALL}\n")
    print("1. 明确输出格式 - 减少格式错误")
    print("2. 展示期望行为 - 提高一致性")
    print("3. 处理边界情况 - 通过示例覆盖\n")
    
    print(f"{Fore.YELLOW}示例数量选择:{Style.RESET_ALL}\n")
    print("Zero-shot (0个):")
    print("  → 适合: 简单任务、通用格式")
    print("  → 风险: 格式不一致\n")
    
    print("One-shot (1个):")
    print("  → 适合: 格式简单、任务明确")
    print("  → 风险: 可能不够全面\n")
    
    print("Few-shot (2-5个):")
    print("  → 适合: 复杂格式、多种情况")
    print("  → 推荐: 大多数场景\n")
    
    print("Many-shot (>5个):")
    print("  → 适合: 极复杂任务")
    print("  → 风险: 浪费 token\n")
    
    print(f"{Fore.GREEN}✓ 设计好示例的技巧:{Style.RESET_ALL}\n")
    print("1. 覆盖典型情况")
    print("2. 包含边界情况（如空值、特殊字符）")
    print("3. 示例多样化（不要太相似）")
    print("4. 格式完全一致")
    print("5. 3-5个示例最佳\n")
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}记住: 示例是最好的说明书{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
