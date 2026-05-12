"""
流式 Function Call 演示
展示如何在流式输出中处理工具调用
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


# 定义工具
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称"
                    }
                },
                "required": ["city"]
            }
        }
    }
]


def execute_tool(tool_name: str, arguments: dict):
    """执行工具"""
    if tool_name == "get_weather":
        city = arguments["city"]
        # 模拟天气数据
        weather_data = {
            "北京": {"temperature": 15, "condition": "晴天"},
            "上海": {"temperature": 20, "condition": "多云"},
            "深圳": {"temperature": 25, "condition": "小雨"},
        }
        return weather_data.get(city, {"error": f"未找到 {city} 的天气信息"})
    
    return {"error": f"未知工具: {tool_name}"}


def streaming_with_function_call(prompt: str):
    """流式请求 + Function Call"""
    
    messages = [{"role": "user", "content": prompt}]
    
    print(f"{Fore.GREEN}问题:{Style.RESET_ALL} {prompt}\n")
    print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 第一次请求
    print(f"{Fore.YELLOW}🤖 AI 思考中...{Style.RESET_ALL}\n")
    
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL_ID,
            "messages": messages,
            "tools": TOOLS,
            "stream": True
        },
        stream=True,
        timeout=60
    )
    
    tool_calls = []
    current_tool_call = None
    
    if response.status_code == 200:
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    
                    if data == '[DONE]':
                        break
                    
                    try:
                        chunk = json.loads(data)
                        
                        if 'choices' in chunk and len(chunk['choices']) > 0:
                            delta = chunk['choices'][0].get('delta', {})
                            
                            # 检查是否有工具调用
                            if 'tool_calls' in delta:
                                for tc in delta['tool_calls']:
                                    index = tc.get('index', 0)
                                    
                                    # 初始化工具调用
                                    if index >= len(tool_calls):
                                        tool_calls.append({
                                            'id': tc.get('id', ''),
                                            'type': tc.get('type', 'function'),
                                            'function': {
                                                'name': '',
                                                'arguments': ''
                                            }
                                        })
                                    
                                    # 更新工具调用信息
                                    if 'id' in tc:
                                        tool_calls[index]['id'] = tc['id']
                                    
                                    if 'function' in tc:
                                        func = tc['function']
                                        if 'name' in func:
                                            tool_calls[index]['function']['name'] = func['name']
                                        if 'arguments' in func:
                                            tool_calls[index]['function']['arguments'] += func['arguments']
                    
                    except json.JSONDecodeError:
                        pass
        
        # 如果有工具调用
        if tool_calls:
            for tool_call in tool_calls:
                function_name = tool_call['function']['name']
                arguments = json.loads(tool_call['function']['arguments'])
                
                print(f"{Fore.YELLOW}🔧 调用工具:{Style.RESET_ALL} {function_name}")
                print(f"{Fore.YELLOW}   参数:{Style.RESET_ALL} {json.dumps(arguments, ensure_ascii=False)}\n")
                
                # 执行工具
                result = execute_tool(function_name, arguments)
                print(f"{Fore.YELLOW}   结果:{Style.RESET_ALL} {json.dumps(result, ensure_ascii=False)}\n")
                
                # 添加到消息历史
                messages.append({
                    "role": "assistant",
                    "tool_calls": [tool_call]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call['id'],
                    "content": json.dumps(result, ensure_ascii=False)
                })
            
            # 第二次请求 - 获取最终答案（流式）
            print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
            print(f"{Fore.YELLOW}🤖 AI 回答:{Style.RESET_ALL}\n")
            
            response2 = requests.post(
                f"{API_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL_ID,
                    "messages": messages,
                    "tools": TOOLS,
                    "stream": True
                },
                stream=True,
                timeout=60
            )
            
            if response2.status_code == 200:
                for line in response2.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data = line[6:]
                            
                            if data == '[DONE]':
                                break
                            
                            try:
                                chunk = json.loads(data)
                                
                                if 'choices' in chunk and len(chunk['choices']) > 0:
                                    delta = chunk['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    
                                    if content:
                                        print(content, end='', flush=True)
                            
                            except json.JSONDecodeError:
                                pass
                
                print()  # 换行


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("流式 Function Call 演示")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 测试
    streaming_with_function_call("北京今天天气怎么样？")
    
    print(f"\n{Fore.CYAN}{'='*60}")
    print("技术要点")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.GREEN}流式 Function Call 的挑战:{Style.RESET_ALL}\n")
    print("1. 工具调用信息是分块传输的")
    print("   - function name 可能分多次传输")
    print("   - arguments 肯定分多次传输")
    print("   - 需要累积完整信息\n")
    
    print("2. 需要两次请求")
    print("   - 第一次: 获取工具调用")
    print("   - 执行工具")
    print("   - 第二次: 获取最终答案（流式）\n")
    
    print("3. 用户体验")
    print("   - 显示 '思考中...'")
    print("   - 显示工具调用过程")
    print("   - 流式显示最终答案\n")
    
    print(f"{Fore.YELLOW}实现要点:{Style.RESET_ALL}\n")
    print("✓ 累积 tool_calls 的所有 delta")
    print("✓ 解析完整的 arguments JSON")
    print("✓ 执行工具后继续流式输出")
    print("✓ 给用户清晰的进度提示\n")


if __name__ == "__main__":
    main()
