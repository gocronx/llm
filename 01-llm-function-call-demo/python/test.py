"""
快速测试脚本
"""

import os
import requests
import json
from dotenv import load_dotenv
from function_definitions import FUNCTION_DEFINITIONS

# 加载配置
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


def test_function_call():
    """测试 Function Call"""
    
    print("\n" + "="*60)
    print("Function Call 测试")
    print("="*60 + "\n")
    
    test_cases = [
        ("天气查询", "北京天气怎么样？", "get_weather"),
        ("数学计算", "156 除以 12", "calculate"),
        ("数据库搜索", "帮我在数据库中搜索笔记本相关的产品", "search_database"),
    ]
    
    results = []
    
    for name, question, expected in test_cases:
        print(f"测试: {name}")
        print(f"问题: {question}")
        
        response = requests.post(
            f"{API_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": question}],
                "tools": [
                    {"type": "function", "function": func}
                    for func in FUNCTION_DEFINITIONS
                ],
                "max_tokens": 500
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            tool_calls = data["choices"][0]["message"].get("tool_calls")
            
            if tool_calls:
                func_name = tool_calls[0]["function"]["name"]
                success = func_name == expected
                print(f"结果: {'✓' if success else '✗'} 调用了 {func_name}\n")
                results.append(success)
            else:
                print(f"结果: ✗ 未调用函数\n")
                results.append(False)
        else:
            print(f"结果: ✗ API 错误\n")
            results.append(False)
    
    print("="*60)
    print(f"测试结果: {sum(results)}/{len(results)} 通过")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_function_call()
