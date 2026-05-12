"""
降级策略演示
展示当主服务失败时的降级方案
"""

import os
import requests
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


# 模拟缓存
CACHE: Dict[str, str] = {}


def call_primary_model(prompt: str, model: str = None) -> str:
    """调用主模型"""
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": model or MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100
        },
        timeout=30
    )
    
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"API Error {response.status_code}")


def call_fallback_model(prompt: str) -> str:
    """调用降级模型（更便宜/更快的模型）"""
    # 这里可以调用更便宜的模型
    # 例如：GPT-4 → GPT-3.5-turbo
    return call_primary_model(prompt, model=MODEL_ID)


def get_cached_response(prompt: str) -> Optional[str]:
    """从缓存获取响应"""
    return CACHE.get(prompt)


def cache_response(prompt: str, response: str):
    """缓存响应"""
    CACHE[prompt] = response


def get_default_response(prompt: str) -> str:
    """返回默认响应"""
    return "抱歉，服务暂时不可用，请稍后再试。"


# ============================================================
# 降级策略 1: 模型降级
# ============================================================

def strategy_model_fallback(prompt: str) -> tuple[str, str]:
    """
    策略 1: 模型降级
    GPT-4 失败 → GPT-3.5-turbo
    """
    try:
        print(f"{Fore.CYAN}尝试主模型...{Style.RESET_ALL}")
        result = call_primary_model(prompt)
        print(f"{Fore.GREEN}✓ 主模型成功{Style.RESET_ALL}")
        return result, "primary"
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  主模型失败: {e}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}尝试降级模型...{Style.RESET_ALL}")
        try:
            result = call_fallback_model(prompt)
            print(f"{Fore.GREEN}✓ 降级模型成功{Style.RESET_ALL}")
            return result, "fallback"
        except Exception as e2:
            print(f"{Fore.RED}✗ 降级模型也失败: {e2}{Style.RESET_ALL}")
            raise


# ============================================================
# 降级策略 2: 缓存降级
# ============================================================

def strategy_cache_fallback(prompt: str) -> tuple[str, str]:
    """
    策略 2: 缓存降级
    API 失败 → 使用缓存
    """
    try:
        print(f"{Fore.CYAN}尝试 API 调用...{Style.RESET_ALL}")
        result = call_primary_model(prompt)
        print(f"{Fore.GREEN}✓ API 成功{Style.RESET_ALL}")
        
        # 缓存结果
        cache_response(prompt, result)
        return result, "api"
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  API 失败: {e}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}尝试从缓存获取...{Style.RESET_ALL}")
        
        cached = get_cached_response(prompt)
        if cached:
            print(f"{Fore.GREEN}✓ 缓存命中{Style.RESET_ALL}")
            return cached, "cache"
        else:
            print(f"{Fore.RED}✗ 缓存未命中{Style.RESET_ALL}")
            raise


# ============================================================
# 降级策略 3: 功能降级
# ============================================================

def strategy_feature_fallback(prompt: str, enable_advanced: bool = True) -> tuple[str, str]:
    """
    策略 3: 功能降级
    完整功能失败 → 基础功能
    """
    if enable_advanced:
        try:
            print(f"{Fore.CYAN}尝试完整功能（高级模型 + 长输出）...{Style.RESET_ALL}")
            result = call_primary_model(prompt)
            print(f"{Fore.GREEN}✓ 完整功能成功{Style.RESET_ALL}")
            return result, "full"
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  完整功能失败: {e}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}降级到基础功能...{Style.RESET_ALL}")
    
    # 基础功能：简化提示词
    try:
        simplified_prompt = prompt[:50]  # 截断提示词
        result = call_primary_model(simplified_prompt)
        print(f"{Fore.GREEN}✓ 基础功能成功{Style.RESET_ALL}")
        return result, "basic"
    except Exception as e:
        print(f"{Fore.RED}✗ 基础功能也失败: {e}{Style.RESET_ALL}")
        raise


# ============================================================
# 降级策略 4: 默认响应
# ============================================================

def strategy_default_response(prompt: str) -> tuple[str, str]:
    """
    策略 4: 默认响应
    所有方法失败 → 返回默认响应
    """
    try:
        print(f"{Fore.CYAN}尝试 API 调用...{Style.RESET_ALL}")
        result = call_primary_model(prompt)
        print(f"{Fore.GREEN}✓ API 成功{Style.RESET_ALL}")
        return result, "api"
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  API 失败: {e}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}返回默认响应...{Style.RESET_ALL}")
        result = get_default_response(prompt)
        print(f"{Fore.GREEN}✓ 返回默认响应{Style.RESET_ALL}")
        return result, "default"


# ============================================================
# 降级策略 5: 多级降级
# ============================================================

def strategy_multi_level_fallback(prompt: str) -> tuple[str, str]:
    """
    策略 5: 多级降级
    主模型 → 降级模型 → 缓存 → 默认响应
    """
    # 第 1 级：主模型
    try:
        print(f"{Fore.CYAN}[级别 1] 尝试主模型...{Style.RESET_ALL}")
        result = call_primary_model(prompt)
        print(f"{Fore.GREEN}✓ 主模型成功{Style.RESET_ALL}")
        cache_response(prompt, result)
        return result, "primary"
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  主模型失败: {e}{Style.RESET_ALL}")
    
    # 第 2 级：降级模型
    try:
        print(f"{Fore.CYAN}[级别 2] 尝试降级模型...{Style.RESET_ALL}")
        result = call_fallback_model(prompt)
        print(f"{Fore.GREEN}✓ 降级模型成功{Style.RESET_ALL}")
        cache_response(prompt, result)
        return result, "fallback"
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  降级模型失败: {e}{Style.RESET_ALL}")
    
    # 第 3 级：缓存
    print(f"{Fore.CYAN}[级别 3] 尝试缓存...{Style.RESET_ALL}")
    cached = get_cached_response(prompt)
    if cached:
        print(f"{Fore.GREEN}✓ 缓存命中{Style.RESET_ALL}")
        return cached, "cache"
    print(f"{Fore.YELLOW}⚠️  缓存未命中{Style.RESET_ALL}")
    
    # 第 4 级：默认响应
    print(f"{Fore.CYAN}[级别 4] 返回默认响应{Style.RESET_ALL}")
    result = get_default_response(prompt)
    print(f"{Fore.GREEN}✓ 返回默认响应{Style.RESET_ALL}")
    return result, "default"


# ============================================================
# 演示
# ============================================================

def demo_model_fallback():
    """演示模型降级"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 1: 模型降级")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}策略: GPT-4 → GPT-3.5-turbo{Style.RESET_ALL}\n")
    
    result, source = strategy_model_fallback("什么是降级策略？")
    print(f"\n{Fore.GREEN}结果 (来源: {source}):{Style.RESET_ALL} {result[:100]}...")


def demo_cache_fallback():
    """演示缓存降级"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 2: 缓存降级")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}策略: API → 缓存{Style.RESET_ALL}\n")
    
    prompt = "1+1=?"
    
    # 第一次调用（会缓存）
    print(f"{Fore.CYAN}第一次调用:{Style.RESET_ALL}")
    result1, source1 = strategy_cache_fallback(prompt)
    print(f"结果 (来源: {source1}): {result1[:50]}...\n")
    
    # 第二次调用（使用缓存）
    print(f"{Fore.CYAN}第二次调用（模拟 API 失败）:{Style.RESET_ALL}")
    result2, source2 = strategy_cache_fallback(prompt)
    print(f"结果 (来源: {source2}): {result2[:50]}...")


def demo_feature_fallback():
    """演示功能降级"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 3: 功能降级")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}策略: 完整功能 → 基础功能{Style.RESET_ALL}\n")
    
    result, source = strategy_feature_fallback("解释量子计算的原理", enable_advanced=True)
    print(f"\n{Fore.GREEN}结果 (来源: {source}):{Style.RESET_ALL} {result[:100]}...")


def demo_default_response():
    """演示默认响应"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 4: 默认响应")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}策略: API → 默认响应{Style.RESET_ALL}\n")
    
    result, source = strategy_default_response("测试问题")
    print(f"\n{Fore.GREEN}结果 (来源: {source}):{Style.RESET_ALL} {result}")


def demo_multi_level():
    """演示多级降级"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 5: 多级降级")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}策略: 主模型 → 降级模型 → 缓存 → 默认响应{Style.RESET_ALL}\n")
    
    result, source = strategy_multi_level_fallback("Python 是什么？")
    print(f"\n{Fore.GREEN}最终结果 (来源: {source}):{Style.RESET_ALL} {result[:100]}...")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("降级策略演示")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}核心概念:{Style.RESET_ALL}")
    print("1. 降级：当主服务失败时，使用备用方案")
    print("2. 优雅降级：保证基本功能可用")
    print("3. 多级降级：多个备用方案，逐级尝试")
    print("4. 用户体验：避免完全失败，提供部分功能\n")
    
    # 演示 1: 模型降级
    demo_model_fallback()
    
    # 演示 2: 缓存降级
    demo_cache_fallback()
    
    # 演示 3: 功能降级
    demo_feature_fallback()
    
    # 演示 4: 默认响应
    demo_default_response()
    
    # 演示 5: 多级降级
    demo_multi_level()
    
    # 总结
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("降级策略对比")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    strategies = [
        ("模型降级", "高质量模型 → 低质量模型", "质量下降，但仍可用"),
        ("缓存降级", "实时 API → 历史缓存", "数据可能过时，但快速"),
        ("功能降级", "完整功能 → 基础功能", "功能受限，但核心可用"),
        ("默认响应", "动态生成 → 静态响应", "通用回复，用户体验差"),
        ("多级降级", "逐级尝试多个方案", "最大化可用性"),
    ]
    
    print(f"{'策略':<15} {'方案':<30} {'特点':<25}")
    print("-" * 70)
    for name, plan, feature in strategies:
        print(f"{name:<15} {plan:<30} {feature:<25}")
    
    print(f"\n{Fore.GREEN}最佳实践:{Style.RESET_ALL}")
    print("  - 根据业务重要性选择降级策略")
    print("  - 监控降级率，及时发现问题")
    print("  - 记录降级日志，便于分析")
    print("  - 定期测试降级方案")
    print("  - 向用户明确说明服务状态\n")


if __name__ == "__main__":
    main()
