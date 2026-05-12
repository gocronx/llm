"""
API 响应格式化示例 - 标准化 API 响应格式
"""

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


def generate_api_response(query: str, schema: dict):
    """生成标准 API 响应"""
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
                    "content": "你是一个 API 服务。根据查询生成标准格式的响应。"
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "api_response",
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
        return json.loads(content)
    else:
        return None


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("API 响应格式化示例")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 标准 API 响应格式
    api_response_schema = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["success", "error"]
            },
            "code": {"type": "integer"},
            "message": {"type": "string"},
            "data": {
                "type": "object",
                "additionalProperties": True
            },
            "timestamp": {"type": "string"}
        },
        "required": ["status", "code", "message"],
        "additionalProperties": False
    }
    
    # 场景 1: 用户查询
    print(f"{Fore.GREEN}场景 1: 用户信息查询{Style.RESET_ALL}\n")
    
    query1 = "查询用户ID为12345的信息"
    
    # 自定义 schema 包含用户数据
    user_query_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["success", "error"]},
            "code": {"type": "integer"},
            "message": {"type": "string"},
            "data": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer"},
                    "username": {"type": "string"},
                    "email": {"type": "string"},
                    "created_at": {"type": "string"},
                    "is_active": {"type": "boolean"}
                },
                "required": ["user_id", "username"],
                "additionalProperties": False
            },
            "timestamp": {"type": "string"}
        },
        "required": ["status", "code", "message", "data"],
        "additionalProperties": False
    }
    
    print(f"{Fore.YELLOW}查询:{Style.RESET_ALL} {query1}\n")
    
    result = generate_api_response(query1, user_query_schema)
    if result:
        print(f"{Fore.GREEN}API 响应:{Style.RESET_ALL}\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 场景 2: 搜索查询
    print(f"{Fore.GREEN}场景 2: 产品搜索{Style.RESET_ALL}\n")
    
    query2 = "搜索价格在5000-10000元的笔记本电脑"
    
    search_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["success", "error"]},
            "code": {"type": "integer"},
            "message": {"type": "string"},
            "data": {
                "type": "object",
                "properties": {
                    "total": {"type": "integer"},
                    "page": {"type": "integer"},
                    "page_size": {"type": "integer"},
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "price": {"type": "number"},
                                "brand": {"type": "string"},
                                "in_stock": {"type": "boolean"}
                            },
                            "required": ["id", "name", "price"],
                            "additionalProperties": False
                        }
                    }
                },
                "required": ["total", "results"],
                "additionalProperties": False
            },
            "timestamp": {"type": "string"}
        },
        "required": ["status", "code", "message", "data"],
        "additionalProperties": False
    }
    
    print(f"{Fore.YELLOW}查询:{Style.RESET_ALL} {query2}\n")
    
    result = generate_api_response(query2, search_schema)
    if result:
        print(f"{Fore.GREEN}API 响应:{Style.RESET_ALL}\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 场景 3: 错误响应
    print(f"{Fore.GREEN}场景 3: 错误响应{Style.RESET_ALL}\n")
    
    query3 = "查询不存在的用户ID 99999"
    
    error_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["success", "error"]},
            "code": {"type": "integer"},
            "message": {"type": "string"},
            "error": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "details": {"type": "string"}
                },
                "required": ["type"],
                "additionalProperties": False
            },
            "timestamp": {"type": "string"}
        },
        "required": ["status", "code", "message"],
        "additionalProperties": False
    }
    
    print(f"{Fore.YELLOW}查询:{Style.RESET_ALL} {query3}\n")
    
    result = generate_api_response(query3, error_schema)
    if result:
        print(f"{Fore.GREEN}API 响应:{Style.RESET_ALL}\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print(f"\n{Fore.CYAN}{'='*60}")
    print("API 响应格式化的价值")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print("✓ 统一响应格式")
    print("✓ 类型安全")
    print("✓ 易于前端处理")
    print("✓ 自动文档生成\n")


if __name__ == "__main__":
    main()
