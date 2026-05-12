"""
对比不同 Prompt Engineering 技术的效果
展示同一任务使用不同技术的差异
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


def compare_code_review():
    """对比代码审查任务 - 重点看格式控制"""
    print_section("任务 1: 格式控制对比（代码审查）")
    
    code = """
def login(username, password):
    if username == "admin" and password == "123456":
        return True
    return False
"""
    
    print(f"{Fore.YELLOW}说明: 这个模型很强，质量差异不大，重点看格式控制{Style.RESET_ALL}\n")
    
    techniques = [
        {
            "name": "❌ 无格式要求",
            "system": "",
            "user": f"审查这段代码:\n{code}",
            "note": "格式随机，难以程序化处理"
        },
        {
            "name": "✅ JSON 格式输出",
            "system": "你是代码审查专家。",
            "user": f"""审查代码并输出 JSON:

{{
  "severity": "high/medium/low",
  "issues": ["问题1", "问题2"],
  "score": 1-10
}}

代码:
{code}

只输出 JSON，不要其他内容。
""",
            "note": "格式固定，便于解析"
        }
    ]
    
    for tech in techniques:
        print(f"{Fore.GREEN}{tech['name']}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}目的: {tech['note']}{Style.RESET_ALL}\n")
        
        response = call_llm(tech['system'], tech['user'])
        print(f"{Fore.YELLOW}输出:{Style.RESET_ALL}")
        print(response[:300] + "..." if len(response) > 300 else response)
        print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")


def compare_data_extraction():
    """对比数据提取任务 - 重点看字段名一致性"""
    print_section("任务 2: 字段名一致性（数据提取）")
    
    text = "张三，28岁，Python工程师，邮箱 zhangsan@example.com，擅长 Django 和 FastAPI"
    
    print(f"{Fore.YELLOW}说明: Few-shot 的价值在于统一字段名（name vs 姓名）{Style.RESET_ALL}\n")
    
    techniques = [
        {
            "name": "❌ Zero-shot（字段名不确定）",
            "system": "",
            "user": f"从文本中提取姓名、年龄、职位、邮箱、技能，输出 JSON:\n{text}",
            "note": "可能用中文字段名，也可能用英文"
        },
        {
            "name": "✅ Few-shot（字段名统一）",
            "system": "",
            "user": f"""提取信息并输出 JSON。

示例:
输入: "李四，30岁，Java开发，邮箱 lisi@example.com，擅长 Spring"
输出: {{"name": "李四", "age": 30, "position": "Java开发", "email": "lisi@example.com", "skills": ["Spring"]}}

现在处理:
输入: {text}
输出:""",
            "note": "字段名固定为英文，便于程序处理"
        }
    ]
    
    for tech in techniques:
        print(f"{Fore.GREEN}{tech['name']}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}目的: {tech['note']}{Style.RESET_ALL}\n")
        
        response = call_llm(tech['system'], tech['user'])
        print(f"{Fore.YELLOW}输出:{Style.RESET_ALL}")
        print(response)
        print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")


def compare_reasoning():
    """对比推理任务 - CoT 的价值在于可验证性"""
    print_section("任务 3: 推理过程可验证性")
    
    problem = "一个班级有 45 个学生，其中 60% 是女生。如果新来 5 个男生，现在男生占多少比例？"
    
    print(f"{Fore.YELLOW}说明: CoT 的价值不是提高准确率（模型已经很准），而是让推理过程可验证{Style.RESET_ALL}\n")
    
    techniques = [
        {
            "name": "❌ 直接给答案（无法验证）",
            "system": "",
            "user": f"{problem}\n\n只给出最终答案，不要解释。",
            "note": "答案对错无法验证"
        },
        {
            "name": "✅ Chain of Thought（可验证）",
            "system": "",
            "user": f"""请一步步思考：

问题: {problem}

思考过程:
1. 原有女生人数 = ?
2. 原有男生人数 = ?
3. 新来后男生人数 = ?
4. 新来后总人数 = ?
5. 男生比例 = ?

答案:""",
            "note": "每一步都可以验证"
        }
    ]
    
    for tech in techniques:
        print(f"{Fore.GREEN}{tech['name']}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}目的: {tech['note']}{Style.RESET_ALL}\n")
        
        response = call_llm(tech['system'], tech['user'])
        print(f"{Fore.YELLOW}输出:{Style.RESET_ALL}")
        print(response)
        print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")


def main():
    print_section("Prompt Engineering 技术对比")
    
    print(f"{Fore.YELLOW}重要说明:{Style.RESET_ALL}")
    print("这个模型（Qwen3.5-27B）本身就很强，所以：")
    print("- 简单 Prompt 和复杂 Prompt 的质量差异不大")
    print("- Prompt Engineering 的价值在于：格式控制、一致性、可验证性")
    print("- 而不是提高回答质量\n")
    
    # 任务 1: 格式控制
    compare_code_review()
    
    # 任务 2: 字段名一致性
    compare_data_extraction()
    
    # 任务 3: 推理可验证性
    compare_reasoning()
    
    # 总结
    print_section("总结")
    
    print(f"{Fore.GREEN}Prompt Engineering 的真正价值:{Style.RESET_ALL}\n")
    
    print("1. 格式控制:")
    print("   - 不是提高质量，而是控制输出格式")
    print("   - JSON vs Markdown vs 自由文本")
    print("   - 便于程序化处理\n")
    
    print("2. 字段名统一:")
    print("   - Few-shot 确保字段名一致")
    print("   - name vs 姓名（英文 vs 中文）")
    print("   - 减少后处理工作\n")
    
    print("3. 推理可验证:")
    print("   - CoT 不是提高准确率（模型已经很准）")
    print("   - 而是让推理过程可验证")
    print("   - 便于发现错误和调试\n")
    
    print(f"{Fore.YELLOW}实际应用建议:{Style.RESET_ALL}\n")
    print("✓ 需要程序处理 → 用 Structured Output")
    print("✓ 需要字段统一 → 用 Few-shot")
    print("✓ 需要验证推理 → 用 Chain of Thought")
    print("✓ 模型已经很强 → 重点放在格式控制，而不是质量提升\n")
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}记住: Prompt Engineering = 格式控制 + 一致性保证{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
