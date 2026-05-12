"""
实战案例: 代码审查
使用 Prompt Engineering 技术构建代码审查工具
"""

import os
import json
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


def review_code(code: str, language: str = "Python") -> str:
    """
    代码审查
    
    使用的 Prompt Engineering 技术:
    1. System Prompt - 定义专家角色
    2. Structured Output - JSON 格式输出
    3. Few-shot - 提供审查示例
    """
    
    # System Prompt: 定义角色和行为
    system = f"""你是资深 {language} 安全工程师，拥有 10 年代码审查经验。

你的职责:
1. 识别安全漏洞（SQL注入、XSS、硬编码密码、权限问题）
2. 评估代码质量（可读性、可维护性、性能）
3. 检查最佳实践（命名规范、错误处理、日志记录）
4. 提供具体的改进建议和修改后的代码

你的风格:
- 专业、客观、建设性
- 先指出严重问题，再提优化建议
- 给出具体的修改方案，不只是指出问题
- 使用中文回答

你不应该:
- 过度批评或使用负面语言
- 给出模糊的建议
- 忽略安全问题
"""
    
    # User Prompt: 结构化输出 + Few-shot
    user = f"""审查以下代码并输出 JSON 格式：

{{
  "score": 1-10,
  "severity": "critical/high/medium/low",
  "strengths": ["优点1", "优点2"],
  "issues": [
    {{
      "type": "security/bug/performance/style",
      "severity": "critical/high/medium/low",
      "line": 行号或null,
      "description": "问题描述",
      "suggestion": "改进建议",
      "fixed_code": "修改后的代码（可选）"
    }}
  ],
  "summary": "一句话总结"
}}

代码:
```{language.lower()}
{code}
```

输出:"""
    
    return call_llm(system, user)


def main():
    print_section("实战案例: 代码审查工具")
    
    # 测试案例 1: 安全问题
    print(f"{Fore.GREEN}案例 1: 安全漏洞检测{Style.RESET_ALL}\n")
    
    code1 = """
def login(username, password):
    # 硬编码密码
    if username == "admin" and password == "123456":
        return True
    
    # SQL 注入风险
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    result = db.execute(query)
    
    return result is not None
"""
    
    print(f"{Fore.YELLOW}待审查代码:{Style.RESET_ALL}")
    print(code1)
    
    print(f"\n{Fore.CYAN}正在审查...{Style.RESET_ALL}\n")
    result = review_code(code1)
    
    print(f"{Fore.CYAN}审查结果:{Style.RESET_ALL}")
    print(result)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 测试案例 2: 性能问题
    print(f"{Fore.GREEN}案例 2: 性能问题检测{Style.RESET_ALL}\n")
    
    code2 = """
def find_duplicates(items):
    duplicates = []
    for i in range(len(items)):
        for j in range(i+1, len(items)):
            if items[i] == items[j] and items[i] not in duplicates:
                duplicates.append(items[i])
    return duplicates
"""
    
    print(f"{Fore.YELLOW}待审查代码:{Style.RESET_ALL}")
    print(code2)
    
    print(f"\n{Fore.CYAN}正在审查...{Style.RESET_ALL}\n")
    result = review_code(code2)
    
    print(f"{Fore.CYAN}审查结果:{Style.RESET_ALL}")
    print(result)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 测试案例 3: 代码质量
    print(f"{Fore.GREEN}案例 3: 代码质量检测{Style.RESET_ALL}\n")
    
    code3 = """
def calc(a, b, op):
    if op == '+':
        return a + b
    elif op == '-':
        return a - b
    elif op == '*':
        return a * b
    elif op == '/':
        return a / b
"""
    
    print(f"{Fore.YELLOW}待审查代码:{Style.RESET_ALL}")
    print(code3)
    
    print(f"\n{Fore.CYAN}正在审查...{Style.RESET_ALL}\n")
    result = review_code(code3)
    
    print(f"{Fore.CYAN}审查结果:{Style.RESET_ALL}")
    print(result)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 总结
    print_section("技术总结")
    
    print(f"{Fore.GREEN}本案例使用的 Prompt Engineering 技术:{Style.RESET_ALL}\n")
    
    print("1. System Prompt:")
    print("   - 定义专家角色（资深安全工程师）")
    print("   - 明确职责范围（安全、质量、最佳实践）")
    print("   - 设定行为风格（专业、建设性）\n")
    
    print("2. Structured Output:")
    print("   - JSON 格式输出")
    print("   - 包含评分、严重程度、问题列表")
    print("   - 便于程序化处理\n")
    
    print("3. 明确要求:")
    print("   - 指定输出字段")
    print("   - 要求提供修改建议")
    print("   - 包含修改后的代码\n")
    
    print(f"{Fore.YELLOW}实际应用价值:{Style.RESET_ALL}\n")
    print("✓ 自动化代码审查")
    print("✓ 发现安全漏洞")
    print("✓ 提高代码质量")
    print("✓ 节省人工审查时间")
    print("✓ 统一审查标准\n")
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}好的 Prompt = 好的工具{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
