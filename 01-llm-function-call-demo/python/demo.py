"""
Function Call 核心演示
"""

import os
import requests
import json
from dotenv import load_dotenv
from function_definitions import FUNCTION_DEFINITIONS, execute_function

# 加载配置
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


def call_llm(messages, functions=None):
    """调用 LLM"""
    payload = {
        "model": MODEL_ID,
        "messages": messages,
        "max_tokens": 1000
    }
    
    if functions:
        payload["tools"] = [
            {"type": "function", "function": func}
            for func in functions
        ]
    
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=60
    )
    
    return response.json() if response.status_code == 200 else None


def run_function_call(user_message: str):
    """运行 Function Call"""
    
    print(f"\n{'='*60}")
    print(f"用户: {user_message}")
    print(f"{'='*60}\n")
    
    messages = [{"role": "user", "content": user_message}]
    
    # 第一次调用：让 LLM 决定是否调用函数
    print("→ 发送请求到 LLM...")
    response = call_llm(messages, FUNCTION_DEFINITIONS)
    
    if not response:
        print("✗ API 调用失败\n")
        return
    
    message = response["choices"][0]["message"]
    tool_calls = message.get("tool_calls")
    
    if tool_calls:
        # LLM 决定调用函数
        tool_call = tool_calls[0]
        func_name = tool_call["function"]["name"]
        func_args = json.loads(tool_call["function"]["arguments"])
        
        print(f"✓ LLM 调用函数: {func_name}")
        print(f"  参数: {json.dumps(func_args, ensure_ascii=False)}\n")
        
        # 执行函数
        print("→ 执行函数...")
        result = execute_function(func_name, func_args)
        print(f"✓ 函数返回: {result}\n")
        
        # 第二次调用：生成最终回答
        messages.append(message)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": func_name,
            "content": result
        })
        
        print("→ 生成最终回答...")
        final_response = call_llm(messages)
        
        if final_response:
            answer = final_response["choices"][0]["message"]["content"]
            print(f"✓ 最终回答:\n{answer}\n")
    else:
        # 直接回答
        content = message.get("content", "")
        print(f"✓ LLM 直接回答:\n{content}\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Function Call Demo")
    print("="*60)
    
    # 示例
    run_function_call("北京今天天气怎么样？")
    run_function_call("156 除以 12 等于多少？")
    run_function_call("搜索价格在500元以上的产品")
