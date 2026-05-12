"""
基础重试演示
展示简单的重试机制和常见错误处理
"""

import os
import time
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


class APIError(Exception):
    """API 错误基类"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")


class RateLimitError(APIError):
    """限流错误（429）"""
    pass


class ServerError(APIError):
    """服务器错误（5xx）"""
    pass


class TimeoutError(APIError):
    """超时错误"""
    pass


def call_llm_no_retry(prompt: str) -> str:
    """不带重试的 LLM 调用（演示失败场景）"""
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100
        },
        timeout=5  # 短超时，容易失败
    )
    
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    elif response.status_code == 429:
        raise RateLimitError(429, "Rate limit exceeded")
    elif response.status_code >= 500:
        raise ServerError(response.status_code, "Server error")
    else:
        raise APIError(response.status_code, response.text)


def call_llm_with_simple_retry(prompt: str, max_retries: int = 3) -> str:
    """带简单重试的 LLM 调用"""
    for attempt in range(max_retries):
        try:
            print(f"{Fore.CYAN}尝试 {attempt + 1}/{max_retries}...{Style.RESET_ALL}")
            
            response = requests.post(
                f"{API_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL_ID,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100
                },
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✓ 成功！{Style.RESET_ALL}")
                return response.json()["choices"][0]["message"]["content"]
            elif response.status_code == 429:
                print(f"{Fore.YELLOW}⚠️  限流错误，等待后重试...{Style.RESET_ALL}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # 固定等待 2 秒
                    continue
                raise RateLimitError(429, "Rate limit exceeded after retries")
            elif response.status_code >= 500:
                print(f"{Fore.YELLOW}⚠️  服务器错误，重试...{Style.RESET_ALL}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                raise ServerError(response.status_code, "Server error after retries")
            else:
                raise APIError(response.status_code, response.text)
                
        except requests.exceptions.Timeout:
            print(f"{Fore.YELLOW}⚠️  请求超时，重试...{Style.RESET_ALL}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            raise TimeoutError(0, "Request timeout after retries")
        except requests.exceptions.ConnectionError:
            print(f"{Fore.YELLOW}⚠️  连接失败，重试...{Style.RESET_ALL}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise APIError(0, "Connection failed after retries")


def demo_no_retry():
    """演示不带重试的情况"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 1: 不带重试（容易失败）")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    try:
        result = call_llm_no_retry("说一个笑话")
        print(f"{Fore.GREEN}成功:{Style.RESET_ALL} {result}")
    except APIError as e:
        print(f"{Fore.RED}失败:{Style.RESET_ALL} {e}")
    except Exception as e:
        print(f"{Fore.RED}失败:{Style.RESET_ALL} {e}")


def demo_simple_retry():
    """演示简单重试"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 2: 简单重试（固定间隔）")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    try:
        result = call_llm_with_simple_retry("用一句话介绍 Python", max_retries=3)
        print(f"\n{Fore.GREEN}最终结果:{Style.RESET_ALL} {result}")
    except APIError as e:
        print(f"\n{Fore.RED}最终失败:{Style.RESET_ALL} {e}")


def demo_error_types():
    """演示不同类型的错误"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 3: 不同类型的错误")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    error_scenarios = [
        ("正常请求", "你好"),
        ("超长请求（可能超时）", "请详细解释" + "非常" * 100 + "详细"),
    ]
    
    for scenario, prompt in error_scenarios:
        print(f"\n{Fore.YELLOW}场景: {scenario}{Style.RESET_ALL}")
        try:
            result = call_llm_with_simple_retry(prompt[:100], max_retries=2)
            print(f"{Fore.GREEN}成功:{Style.RESET_ALL} {result[:50]}...")
        except Exception as e:
            print(f"{Fore.RED}失败:{Style.RESET_ALL} {type(e).__name__}: {e}")


def demo_retry_statistics():
    """演示重试统计"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 4: 重试统计")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    stats = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "retries": 0
    }
    
    test_prompts = [
        "1+1=?",
        "Python 是什么？",
        "说个笑话",
        "今天天气怎么样？",
        "推荐一本书"
    ]
    
    for prompt in test_prompts:
        stats["total"] += 1
        print(f"\n{Fore.CYAN}测试 {stats['total']}: {prompt}{Style.RESET_ALL}")
        
        try:
            result = call_llm_with_simple_retry(prompt, max_retries=3)
            stats["success"] += 1
            print(f"{Fore.GREEN}✓ 成功{Style.RESET_ALL}")
        except Exception as e:
            stats["failed"] += 1
            print(f"{Fore.RED}✗ 失败: {type(e).__name__}{Style.RESET_ALL}")
    
    # 显示统计
    print(f"\n{Fore.CYAN}{'='*60}")
    print("统计结果")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"总请求数: {stats['total']}")
    print(f"成功: {stats['success']} ({stats['success']/stats['total']*100:.1f}%)")
    print(f"失败: {stats['failed']} ({stats['failed']/stats['total']*100:.1f}%)")
    
    if stats['success'] > 0:
        success_rate = stats['success'] / stats['total'] * 100
        if success_rate >= 90:
            print(f"\n{Fore.GREEN}✓ 成功率良好{Style.RESET_ALL}")
        elif success_rate >= 70:
            print(f"\n{Fore.YELLOW}⚠️  成功率一般，建议优化{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.RED}✗ 成功率较低，需要改进{Style.RESET_ALL}")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("基础重试演示")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}核心概念:{Style.RESET_ALL}")
    print("1. 不是所有错误都应该重试")
    print("2. 重试要有次数限制")
    print("3. 重试要有间隔（避免雷鸣群效应）")
    print("4. 记录重试统计，监控系统健康\n")
    
    # 演示 1: 不带重试
    demo_no_retry()
    
    # 演示 2: 简单重试
    demo_simple_retry()
    
    # 演示 3: 不同错误类型
    demo_error_types()
    
    # 演示 4: 重试统计
    demo_retry_statistics()
    
    # 总结
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("最佳实践")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}应该重试的错误:{Style.RESET_ALL}")
    print("  ✅ 429 Rate Limit（限流）")
    print("  ✅ 500/502/503/504（服务器错误）")
    print("  ✅ Timeout（超时）")
    print("  ✅ Connection Error（连接错误）\n")
    
    print(f"{Fore.YELLOW}不应该重试的错误:{Style.RESET_ALL}")
    print("  ❌ 400 Bad Request（请求格式错误）")
    print("  ❌ 401 Unauthorized（认证失败）")
    print("  ❌ 403 Forbidden（权限不足）")
    print("  ❌ 404 Not Found（资源不存在）\n")
    
    print(f"{Fore.GREEN}建议:{Style.RESET_ALL}")
    print("  - 使用指数退避而不是固定间隔")
    print("  - 添加抖动避免雷鸣群效应")
    print("  - 设置最大重试次数（通常 3-5 次）")
    print("  - 记录重试日志，监控系统健康\n")


if __name__ == "__main__":
    main()
