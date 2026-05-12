"""
表单填充示例 - 将自然语言转换为标准表单
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


def fill_form(user_input: str, schema: dict):
    """将用户输入转换为标准表单"""
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
                    "content": "你是一个表单填写助手。根据用户的自然语言描述，填写标准表单。"
                },
                {
                    "role": "user",
                    "content": user_input
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "form_data",
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
    print("表单填充示例")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 场景 1: 用户注册表单
    print(f"{Fore.GREEN}场景 1: 用户注册表单{Style.RESET_ALL}\n")
    
    user_input = """
    我叫王芳，今年25岁，女性。
    我住在北京市朝阳区建国路88号，邮编100020。
    手机号是13900139000，邮箱是wangfang@example.com。
    我想注册一个账号，用户名用wangfang123，密码设置为Abc@123456。
    我同意服务条款。
    """
    
    registration_schema = {
        "type": "object",
        "properties": {
            "personal_info": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                    "gender": {
                        "type": "string",
                        "enum": ["male", "female", "other"]
                    }
                },
                "required": ["name", "age", "gender"],
                "additionalProperties": False
            },
            "address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "postal_code": {"type": "string"}
                },
                "required": ["city"],
                "additionalProperties": False
            },
            "contact": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                    "email": {"type": "string"}
                },
                "required": ["phone", "email"],
                "additionalProperties": False
            },
            "account": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "password": {"type": "string"}
                },
                "required": ["username", "password"],
                "additionalProperties": False
            },
            "terms_accepted": {"type": "boolean"}
        },
        "required": ["personal_info", "contact", "account", "terms_accepted"],
        "additionalProperties": False
    }
    
    print(f"{Fore.YELLOW}用户输入:{Style.RESET_ALL}\n{user_input}\n")
    
    result = fill_form(user_input, registration_schema)
    if result:
        print(f"{Fore.GREEN}表单数据:{Style.RESET_ALL}\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 场景 2: 订单表单
    print(f"{Fore.GREEN}场景 2: 订单表单{Style.RESET_ALL}\n")
    
    order_input = """
    我要买2个iPhone 15 Pro，每个9999元，还要买1个AirPods Pro，2999元。
    配送地址是上海市浦东新区陆家嘴环路1000号，收件人张伟，电话13800138000。
    用支付宝付款，需要发票，公司名称是上海科技有限公司。
    备注：请在工作日送货。
    """
    
    order_schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_name": {"type": "string"},
                        "quantity": {"type": "integer"},
                        "unit_price": {"type": "number"}
                    },
                    "required": ["product_name", "quantity", "unit_price"],
                    "additionalProperties": False
                }
            },
            "shipping_address": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "phone": {"type": "string"},
                    "address": {"type": "string"}
                },
                "required": ["recipient", "phone", "address"],
                "additionalProperties": False
            },
            "payment": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["alipay", "wechat", "credit_card", "cash"]
                    },
                    "invoice_required": {"type": "boolean"},
                    "company_name": {"type": "string"}
                },
                "required": ["method"],
                "additionalProperties": False
            },
            "notes": {"type": "string"}
        },
        "required": ["items", "shipping_address", "payment"],
        "additionalProperties": False
    }
    
    print(f"{Fore.YELLOW}用户输入:{Style.RESET_ALL}\n{order_input}\n")
    
    result = fill_form(order_input, order_schema)
    if result:
        print(f"{Fore.GREEN}订单数据:{Style.RESET_ALL}\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 计算总价
        if "items" in result:
            total = sum(item["quantity"] * item["unit_price"] for item in result["items"])
            print(f"\n{Fore.CYAN}订单总价: ¥{total:,.2f}{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}{'='*60}")
    print("表单填充的价值")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print("✓ 自然语言交互")
    print("✓ 减少表单填写负担")
    print("✓ 自动数据验证")
    print("✓ 提升用户体验\n")


if __name__ == "__main__":
    main()
