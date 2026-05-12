"""
数据提取示例 - 从非结构化文本中提取结构化数据
"""

import os
import json
import requests
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


def extract_data(text: str, schema: dict):
    """使用结构化输出提取数据"""
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
                    "content": "你是一个数据提取专家。从文本中提取信息并以结构化格式返回。"
                },
                {
                    "role": "user",
                    "content": f"从以下文本中提取信息：\n\n{text}"
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "extracted_data",
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
    print("数据提取示例")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 场景 1: 简历信息提取
    print(f"{Fore.GREEN}场景 1: 简历信息提取{Style.RESET_ALL}\n")
    
    resume_text = """
    李明，30岁，全栈工程师，拥有5年开发经验。
    联系方式：liming@example.com，电话：13800138000
    技能：Python, JavaScript, React, Django, PostgreSQL
    教育背景：清华大学计算机科学学士（2015-2019）
    工作经历：
    - 2019-2021：字节跳动，后端工程师
    - 2021-至今：阿里巴巴，全栈工程师
    """
    
    resume_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "position": {"type": "string"},
            "experience_years": {"type": "integer"},
            "email": {"type": "string"},
            "phone": {"type": "string"},
            "skills": {
                "type": "array",
                "items": {"type": "string"}
            },
            "education": {
                "type": "object",
                "properties": {
                    "school": {"type": "string"},
                    "degree": {"type": "string"},
                    "years": {"type": "string"}
                },
                "required": ["school", "degree"],
                "additionalProperties": False
            },
            "work_history": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "company": {"type": "string"},
                        "position": {"type": "string"},
                        "period": {"type": "string"}
                    },
                    "required": ["company", "position"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["name", "age", "position", "email"],
        "additionalProperties": False
    }
    
    print(f"{Fore.YELLOW}输入文本:{Style.RESET_ALL}\n{resume_text}\n")
    
    result = extract_data(resume_text, resume_schema)
    if result:
        print(f"{Fore.GREEN}提取结果:{Style.RESET_ALL}\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 场景 2: 产品信息提取
    print(f"{Fore.GREEN}场景 2: 产品信息提取{Style.RESET_ALL}\n")
    
    product_text = """
    iPhone 15 Pro Max，苹果公司最新旗舰手机。
    价格：9999元起
    颜色：钛金属黑、钛金属白、钛金属蓝、钛金属原色
    存储：256GB、512GB、1TB
    特点：A17 Pro芯片、钛金属边框、动作按钮、USB-C接口
    评分：4.8/5.0（基于1000+用户评价）
    库存状态：有货
    """
    
    product_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "brand": {"type": "string"},
            "category": {"type": "string"},
            "price": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "currency": {"type": "string"}
                },
                "required": ["amount", "currency"],
                "additionalProperties": False
            },
            "colors": {
                "type": "array",
                "items": {"type": "string"}
            },
            "storage_options": {
                "type": "array",
                "items": {"type": "string"}
            },
            "features": {
                "type": "array",
                "items": {"type": "string"}
            },
            "rating": {
                "type": "object",
                "properties": {
                    "score": {"type": "number"},
                    "max_score": {"type": "number"},
                    "review_count": {"type": "integer"}
                },
                "required": ["score"],
                "additionalProperties": False
            },
            "in_stock": {"type": "boolean"}
        },
        "required": ["name", "brand", "price"],
        "additionalProperties": False
    }
    
    print(f"{Fore.YELLOW}输入文本:{Style.RESET_ALL}\n{product_text}\n")
    
    result = extract_data(product_text, product_schema)
    if result:
        print(f"{Fore.GREEN}提取结果:{Style.RESET_ALL}\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print(f"\n{Fore.CYAN}{'='*60}")
    print("数据提取的价值")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print("✓ 自动化数据录入")
    print("✓ 减少人工错误")
    print("✓ 统一数据格式")
    print("✓ 提高处理效率\n")


if __name__ == "__main__":
    main()
