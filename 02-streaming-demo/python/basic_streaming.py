"""
基础 Streaming 演示
对比非流式 vs 流式输出
"""

import os
import time
import requests
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


def non_streaming_request(prompt: str):
    """非流式请求 - 等待完整响应"""
    print(f"{Fore.YELLOW}非流式输出（等待完整响应）:{Style.RESET_ALL}\n")
    
    start_time = time.time()
    
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        },
        timeout=60
    )
    
    wait_time = time.time() - start_time
    
    if response.status_code == 200:
        content = response.json()["choices"][0]["message"]["content"]
        print(f"{Fore.CYAN}[等待 {wait_time:.1f}秒]{Style.RESET_ALL}")
        print(content)
    else:
        print(f"{Fore.RED}错误: {response.status_code}{Style.RESET_ALL}")


def streaming_request(prompt: str):
    """流式请求 - 逐字输出"""
    print(f"\n{Fore.YELLOW}流式输出（逐字显示）:{Style.RESET_ALL}\n")
    
    start_time = time.time()
    first_token_time = None
    token_count = 0
    
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True
        },
        stream=True,
        timeout=60
    )
    
    if response.status_code == 200:
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]  # 去掉 'data: ' 前缀
                    
                    if data == '[DONE]':
                        break
                    
                    try:
                        import json
                        chunk = json.loads(data)
                        
                        if 'choices' in chunk and len(chunk['choices']) > 0:
                            delta = chunk['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            
                            if content:
                                if first_token_time is None:
                                    first_token_time = time.time() - start_time
                                
                                print(content, end='', flush=True)
                                token_count += 1
                    
                    except json.JSONDecodeError:
                        pass
        
        print()  # 换行
        
        total_time = time.time() - start_time
        print(f"\n{Fore.CYAN}[首字时间: {first_token_time:.1f}秒, 总时间: {total_time:.1f}秒, Token数: {token_count}]{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}错误: {response.status_code}{Style.RESET_ALL}")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("Streaming 对比演示")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    prompt = "请写一个关于人工智能的简短介绍，包括定义、应用和未来发展。"
    
    print(f"{Fore.GREEN}问题:{Style.RESET_ALL} {prompt}\n")
    print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 非流式
    non_streaming_request(prompt)
    
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}")
    
    # 流式
    streaming_request(prompt)
    
    # 总结
    print(f"\n{Fore.CYAN}{'='*60}")
    print("对比总结")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}非流式输出:{Style.RESET_ALL}")
    print("  优点: 实现简单")
    print("  缺点: 用户需要等待完整响应（5-10秒）")
    print("       感觉很慢，体验差\n")
    
    print(f"{Fore.YELLOW}流式输出:{Style.RESET_ALL}")
    print("  优点: 立即开始显示（0.5-1秒）")
    print("       用户感觉很快，体验好")
    print("  缺点: 实现稍复杂\n")
    
    print(f"{Fore.GREEN}结论:{Style.RESET_ALL}")
    print("  生产环境必须使用流式输出！")
    print("  用户体验差异巨大。\n")


if __name__ == "__main__":
    main()
