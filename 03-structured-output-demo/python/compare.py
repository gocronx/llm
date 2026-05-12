"""
结构化输出 vs 普通 JSON 对比演示
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


def normal_json_output(prompt: str):
    """普通 JSON 输出（可能格式错误）"""
    print(f"{Fore.YELLOW}❌ 普通 JSON 输出（不保证格式）:{Style.RESET_ALL}\n")
    
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL_ID,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个数据提取助手。请以 JSON 格式返回结果。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        },
        timeout=60
    )
    
    if response.status_code == 200:
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        print(f"{Fore.CYAN}输出:{Style.RESET_ALL}\n{content}\n")
        
        # 尝试解析 JSON
        try:
            # 提取 JSON（可能在 markdown 代码块中）
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
            
            parsed = json.loads(json_str)
            print(f"{Fore.GREEN}✓ JSON 解析成功{Style.RESET_ALL}")
            print(f"解析结果: {json.dumps(parsed, ensure_ascii=False, indent=2)}\n")
            return parsed
        except json.JSONDecodeError as e:
            print(f"{Fore.RED}✗ JSON 解析失败: {e}{Style.RESET_ALL}\n")
            return None
    else:
        print(f"{Fore.RED}API 错误: {response.status_code}{Style.RESET_ALL}\n")
        return None


def structured_output(prompt: str, schema: dict):
    """结构化输出（保证格式正确）"""
    print(f"{Fore.YELLOW}✅ 结构化输出（保证格式）:{Style.RESET_ALL}\n")
    
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL_ID,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个数据提取助手。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "user_info",
                    "schema": schema,
                    "strict": True
                }
            }
        },
        timeout=60
    )
    
    if response.status_code == 200:
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        print(f"{Fore.CYAN}输出:{Style.RESET_ALL}\n{content}\n")
        
        # 解析 JSON
        try:
            parsed = json.loads(content)
            print(f"{Fore.GREEN}✓ JSON 解析成功（格式保证正确）{Style.RESET_ALL}")
            print(f"解析结果: {json.dumps(parsed, ensure_ascii=False, indent=2)}\n")
            return parsed
        except json.JSONDecodeError as e:
            print(f"{Fore.RED}✗ JSON 解析失败: {e}{Style.RESET_ALL}\n")
            return None
    else:
        print(f"{Fore.RED}API 错误: {response.status_code}{Style.RESET_ALL}\n")
        return None


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("结构化输出 vs 普通 JSON 对比")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 定义 JSON Schema
    schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "姓名"
            },
            "age": {
                "type": "integer",
                "description": "年龄"
            },
            "position": {
                "type": "string",
                "description": "职位"
            },
            "email": {
                "type": "string",
                "description": "邮箱"
            },
            "skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "技能列表"
            }
        },
        "required": ["name", "age", "position", "email"],
        "additionalProperties": False
    }
    
    prompt = "从以下文本中提取信息：张三，28岁，Python工程师，邮箱zhangsan@example.com，擅长Django和FastAPI"
    
    print(f"{Fore.GREEN}任务:{Style.RESET_ALL} {prompt}\n")
    print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 普通 JSON 输出
    normal_result = normal_json_output(prompt)
    
    print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 结构化输出
    structured_result = structured_output(prompt, schema)
    
    # 对比总结
    print(f"{Fore.CYAN}{'='*60}")
    print("对比总结")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}普通 JSON 输出:{Style.RESET_ALL}")
    print("  问题:")
    print("    - 可能包含 markdown 格式")
    print("    - 可能有额外的说明文字")
    print("    - 字段名可能不一致")
    print("    - 类型可能不匹配（如年龄是字符串）")
    print("    - 可能缺少必需字段\n")
    
    print(f"{Fore.YELLOW}结构化输出:{Style.RESET_ALL}")
    print("  优势:")
    print("    ✓ 100% 符合 JSON Schema")
    print("    ✓ 纯 JSON，无额外格式")
    print("    ✓ 字段名严格匹配")
    print("    ✓ 类型严格匹配")
    print("    ✓ 必需字段保证存在")
    print("    ✓ 可以禁止额外字段\n")
    
    print(f"{Fore.GREEN}结论:{Style.RESET_ALL}")
    print("  结构化输出是生产环境的最佳选择")
    print("  特别适合需要严格格式的场景\n")


if __name__ == "__main__":
    main()
