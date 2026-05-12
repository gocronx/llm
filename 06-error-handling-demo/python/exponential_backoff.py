"""
指数退避演示
展示更智能的重试策略：指数退避 + 抖动
"""

import os
import time
import random
import requests
from typing import Optional, Callable
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


def call_llm_with_exponential_backoff(
    prompt: str,
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
) -> str:
    """
    使用指数退避的 LLM 调用
    
    参数:
        prompt: 提示词
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数基数（通常是 2）
        jitter: 是否添加抖动
    """
    
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
            
            # 需要重试的错误
            if response.status_code in [429, 500, 502, 503, 504]:
                if attempt < max_retries - 1:
                    # 计算延迟时间（指数退避）
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # 添加抖动（随机化延迟时间）
                    if jitter:
                        delay = delay * (0.5 + random.random())  # 50%-150% 的随机范围
                    
                    print(f"{Fore.YELLOW}⚠️  错误 {response.status_code}，等待 {delay:.2f} 秒后重试...{Style.RESET_ALL}")
                    time.sleep(delay)
                    continue
                else:
                    raise Exception(f"API Error {response.status_code} after {max_retries} retries")
            else:
                raise Exception(f"API Error {response.status_code}: {response.text}")
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                delay = min(base_delay * (exponential_base ** attempt), max_delay)
                if jitter:
                    delay = delay * (0.5 + random.random())
                print(f"{Fore.YELLOW}⚠️  超时，等待 {delay:.2f} 秒后重试...{Style.RESET_ALL}")
                time.sleep(delay)
                continue
            raise Exception("Timeout after retries")
        
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                delay = min(base_delay * (exponential_base ** attempt), max_delay)
                if jitter:
                    delay = delay * (0.5 + random.random())
                print(f"{Fore.YELLOW}⚠️  连接失败，等待 {delay:.2f} 秒后重试...{Style.RESET_ALL}")
                time.sleep(delay)
                continue
            raise Exception("Connection failed after retries")
    
    raise Exception("Max retries exceeded")


def demo_fixed_vs_exponential():
    """对比固定间隔 vs 指数退避"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 1: 固定间隔 vs 指数退避")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}固定间隔（每次等待 2 秒）:{Style.RESET_ALL}")
    delays_fixed = [2, 2, 2, 2, 2]
    for i, delay in enumerate(delays_fixed, 1):
        print(f"  尝试 {i}: 等待 {delay} 秒")
    print(f"  总等待时间: {sum(delays_fixed)} 秒\n")
    
    print(f"{Fore.YELLOW}指数退避（基础 1 秒，指数 2）:{Style.RESET_ALL}")
    delays_exponential = [1 * (2 ** i) for i in range(5)]
    for i, delay in enumerate(delays_exponential, 1):
        print(f"  尝试 {i}: 等待 {delay} 秒")
    print(f"  总等待时间: {sum(delays_exponential)} 秒\n")
    
    print(f"{Fore.GREEN}优势:{Style.RESET_ALL}")
    print("  ✅ 快速失败：前几次重试很快")
    print("  ✅ 避免过载：后续重试间隔更长")
    print("  ✅ 自适应：根据失败次数调整策略\n")


def demo_with_without_jitter():
    """对比有无抖动"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 2: 有无抖动（Jitter）")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}无抖动（所有客户端同时重试）:{Style.RESET_ALL}")
    base_delay = 4.0
    for i in range(5):
        delay = base_delay * (2 ** i)
        print(f"  客户端 {i+1}: {delay} 秒")
    print(f"  ⚠️  问题：所有客户端在相同时间重试（雷鸣群效应）\n")
    
    print(f"{Fore.YELLOW}有抖动（随机化延迟）:{Style.RESET_ALL}")
    random.seed(42)  # 固定种子以便演示
    for i in range(5):
        delay = base_delay * (2 ** i)
        jittered_delay = delay * (0.5 + random.random())
        print(f"  客户端 {i+1}: {jittered_delay:.2f} 秒（原始 {delay} 秒）")
    print(f"  ✅ 优势：客户端在不同时间重试，分散负载\n")


def demo_real_retry():
    """实际重试演示"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 3: 实际重试（指数退避 + 抖动）")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    try:
        result = call_llm_with_exponential_backoff(
            "用一句话解释什么是指数退避",
            max_retries=5,
            base_delay=1.0,
            exponential_base=2.0,
            jitter=True
        )
        print(f"\n{Fore.GREEN}最终结果:{Style.RESET_ALL} {result}")
    except Exception as e:
        print(f"\n{Fore.RED}最终失败:{Style.RESET_ALL} {e}")


def demo_different_strategies():
    """对比不同策略"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 4: 不同重试策略对比")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    strategies = [
        ("激进策略", {"base_delay": 0.5, "exponential_base": 1.5, "max_retries": 3}),
        ("平衡策略", {"base_delay": 1.0, "exponential_base": 2.0, "max_retries": 5}),
        ("保守策略", {"base_delay": 2.0, "exponential_base": 2.5, "max_retries": 7}),
    ]
    
    for name, params in strategies:
        print(f"\n{Fore.YELLOW}{name}:{Style.RESET_ALL}")
        print(f"  基础延迟: {params['base_delay']} 秒")
        print(f"  指数基数: {params['exponential_base']}")
        print(f"  最大重试: {params['max_retries']} 次")
        
        delays = []
        for i in range(params['max_retries']):
            delay = params['base_delay'] * (params['exponential_base'] ** i)
            delays.append(delay)
        
        print(f"  延迟序列: {[f'{d:.1f}s' for d in delays]}")
        print(f"  总等待时间: {sum(delays):.1f} 秒")


def demo_with_tenacity():
    """使用 tenacity 库的演示"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 5: 使用 tenacity 库（推荐）")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    try:
        from tenacity import (
            retry,
            stop_after_attempt,
            wait_exponential,
            retry_if_exception_type,
            before_sleep_log
        )
        import logging
        
        # 设置日志
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        
        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=60),
            retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError)),
            before_sleep=before_sleep_log(logger, logging.INFO)
        )
        def call_llm_with_tenacity(prompt: str) -> str:
            """使用 tenacity 装饰器的 LLM 调用"""
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
                return response.json()["choices"][0]["message"]["content"]
            elif response.status_code in [429, 500, 502, 503, 504]:
                raise requests.exceptions.ConnectionError(f"Retryable error: {response.status_code}")
            else:
                raise Exception(f"Non-retryable error: {response.status_code}")
        
        print(f"{Fore.YELLOW}使用 tenacity 库的优势:{Style.RESET_ALL}")
        print("  ✅ 声明式配置，代码简洁")
        print("  ✅ 内置多种重试策略")
        print("  ✅ 自动日志记录")
        print("  ✅ 灵活的条件判断\n")
        
        result = call_llm_with_tenacity("什么是 tenacity？")
        print(f"\n{Fore.GREEN}结果:{Style.RESET_ALL} {result}")
        
    except ImportError:
        print(f"{Fore.YELLOW}⚠️  tenacity 未安装{Style.RESET_ALL}")
        print("安装: pip install tenacity")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("指数退避演示")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}核心概念:{Style.RESET_ALL}")
    print("1. 指数退避：每次重试的等待时间呈指数增长")
    print("2. 抖动（Jitter）：随机化延迟时间，避免雷鸣群效应")
    print("3. 最大延迟：设置上限，避免等待过长")
    print("4. 快速失败：前几次重试很快，后续逐渐变慢\n")
    
    # 演示 1: 固定 vs 指数
    demo_fixed_vs_exponential()
    
    # 演示 2: 有无抖动
    demo_with_without_jitter()
    
    # 演示 3: 实际重试
    demo_real_retry()
    
    # 演示 4: 不同策略
    demo_different_strategies()
    
    # 演示 5: tenacity 库
    demo_with_tenacity()
    
    # 总结
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("最佳实践")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}推荐配置:{Style.RESET_ALL}")
    print("  - 基础延迟: 1 秒")
    print("  - 指数基数: 2")
    print("  - 最大延迟: 60 秒")
    print("  - 最大重试: 5 次")
    print("  - 启用抖动: 是\n")
    
    print(f"{Fore.GREEN}公式:{Style.RESET_ALL}")
    print("  delay = min(base_delay * (exponential_base ** attempt), max_delay)")
    print("  if jitter: delay = delay * (0.5 + random())\n")
    
    print(f"{Fore.GREEN}建议:{Style.RESET_ALL}")
    print("  - 使用 tenacity 库简化实现")
    print("  - 根据业务场景调整参数")
    print("  - 监控重试率，及时发现问题")
    print("  - 记录重试日志，便于排查\n")


if __name__ == "__main__":
    main()
