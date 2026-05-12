"""
Structured Output 技术演示
控制输出格式，便于程序处理
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


def validate_json(text: str) -> bool:
    """验证是否为有效 JSON"""
    try:
        # 尝试提取 JSON（可能包含在其他文本中）
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end > start:
            json_str = text[start:end]
            json.loads(json_str)
            return True
        return False
    except:
        return False


def main():
    print_section("Structured Output 技术演示")
    
    code = """
def calculate_discount(price, discount):
    return price * discount
"""
    
    # 示例 1: 自由格式输出
    print(f"{Fore.GREEN}示例 1: 自由格式输出{Style.RESET_ALL}\n")
    prompt_free = f"分析这段代码的问题:\n{code}"
    print(f"{Fore.YELLOW}Prompt:{Style.RESET_ALL} {prompt_free}\n")
    
    response = call_llm("", prompt_free)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.RED}问题: 格式不固定，难以程序化处理{Style.RESET_ALL}")
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 示例 2: JSON 格式输出
    print(f"{Fore.GREEN}示例 2: JSON 格式输出{Style.RESET_ALL}\n")
    prompt_json = f"""分析代码并输出 JSON 格式：

{{
  "severity": "high/medium/low",
  "issues": [
    {{
      "type": "bug/performance/security/style",
      "line": 行号,
      "description": "问题描述",
      "suggestion": "改进建议"
    }}
  ],
  "summary": "总体评价"
}}

代码:
{code}

输出:"""
    print(f"{Fore.YELLOW}Prompt:{Style.RESET_ALL}")
    print(prompt_json[:150] + "...")
    print()
    
    response = call_llm("", prompt_json)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    
    is_valid = validate_json(response)
    if is_valid:
        print(f"\n{Fore.GREEN}✓ 有效的 JSON 格式{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.RED}✗ 不是有效的 JSON{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 示例 3: Markdown 表格输出
    print(f"{Fore.GREEN}示例 3: Markdown 表格输出{Style.RESET_ALL}\n")
    prompt_table = f"""分析代码并以 Markdown 表格格式输出：

| 行号 | 问题类型 | 严重程度 | 描述 | 建议 |
|------|---------|---------|------|------|
| ... | ... | ... | ... | ... |

代码:
{code}

输出:"""
    print(f"{Fore.YELLOW}Prompt:{Style.RESET_ALL}")
    print(prompt_table[:100] + "...")
    print()
    
    response = call_llm("", prompt_table)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 示例 4: 固定格式输出
    print(f"{Fore.GREEN}示例 4: 固定格式输出{Style.RESET_ALL}\n")
    prompt_fixed = f"""分析代码并按以下格式输出：

【严重程度】: 高/中/低
【问题数量】: X 个

【问题列表】:
1. [类型] 问题描述
   建议: 具体建议

【总结】: 一句话总结

代码:
{code}

输出:"""
    print(f"{Fore.YELLOW}Prompt:{Style.RESET_ALL}")
    print(prompt_fixed[:100] + "...")
    print()
    
    response = call_llm("", prompt_fixed)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 总结
    print_section("Structured Output 要点")
    
    print(f"{Fore.GREEN}✓ 为什么需要结构化输出?{Style.RESET_ALL}\n")
    print("1. 便于程序解析 - 自动化处理")
    print("2. 格式一致 - 减少后处理")
    print("3. 易于验证 - 检查完整性")
    print("4. 可组合 - 多个步骤串联\n")
    
    print(f"{Fore.YELLOW}常见输出格式:{Style.RESET_ALL}\n")
    
    print("1. JSON:")
    print("   优点: 标准格式，易解析")
    print("   适合: API 返回、数据提取")
    print("   示例: {\"name\": \"张三\", \"age\": 28}\n")
    
    print("2. Markdown:")
    print("   优点: 可读性好，支持格式")
    print("   适合: 文档生成、报告")
    print("   示例: ## 标题\\n- 列表项\n")
    
    print("3. 表格:")
    print("   优点: 结构清晰，对比方便")
    print("   适合: 数据对比、统计")
    print("   示例: | 列1 | 列2 |\\n|-----|-----|\n")
    
    print("4. 固定格式:")
    print("   优点: 自定义，灵活")
    print("   适合: 特定业务需求")
    print("   示例: 【标题】: 内容\n")
    
    print(f"{Fore.GREEN}✓ 设计结构化输出的技巧:{Style.RESET_ALL}\n")
    print("1. 明确指定格式 - 给出完整示例")
    print("2. 使用分隔符 - 便于解析")
    print("3. 包含必填字段 - 确保完整性")
    print("4. 验证输出 - 检查格式正确性")
    print("5. 提供默认值 - 处理缺失情况\n")
    
    print(f"{Fore.YELLOW}效果对比:{Style.RESET_ALL}\n")
    print("自由格式:")
    print("  → 灵活，但不一致")
    print("  → 难以自动化处理\n")
    
    print("结构化输出:")
    print("  → 格式固定，易解析")
    print("  → 可自动化处理")
    print("  → 提高系统可靠性 50%+\n")
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}记住: 结构化输出是 AI 与程序的桥梁{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
