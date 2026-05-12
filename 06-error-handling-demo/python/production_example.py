"""
生产级示例
整合所有错误处理策略的完整实现
"""

import os
import time
import random
import requests
from enum import Enum
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


class CircuitState(Enum):
    """断路器状态"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ProductionLLMClient:
    """
    生产级 LLM 客户端
    
    特性:
    1. 指数退避重试
    2. 断路器保护
    3. 多级降级
    4. 监控和日志
    5. 缓存支持
    """
    
    def __init__(
        self,
        api_base_url: str,
        api_key: str,
        model_id: str,
        # 重试配置
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        # 断路器配置
        failure_threshold: int = 5,
        circuit_timeout: float = 60.0,
        success_threshold: int = 2,
        # 降级配置
        enable_fallback: bool = True,
        enable_cache: bool = True
    ):
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.model_id = model_id
        
        # 重试配置
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        
        # 断路器
        self.circuit_state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.failure_threshold = failure_threshold
        self.circuit_timeout = circuit_timeout
        self.success_threshold = success_threshold
        
        # 降级配置
        self.enable_fallback = enable_fallback
        self.enable_cache = enable_cache
        
        # 缓存
        self.cache: Dict[str, str] = {}
        
        # 统计
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "retries": 0,
            "circuit_breaks": 0,
            "cache_hits": 0,
            "fallback_uses": 0
        }
    
    def chat(self, prompt: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        发送聊天请求
        
        返回:
            {
                "success": bool,
                "content": str,
                "source": str,  # "api", "cache", "fallback", "default"
                "attempts": int,
                "error": Optional[str]
            }
        """
        self.stats["total_requests"] += 1
        
        # 检查断路器
        if self.circuit_state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.circuit_state = CircuitState.HALF_OPEN
                self.success_count = 0
                print(f"{Fore.YELLOW}🔄 断路器: OPEN → HALF_OPEN{Style.RESET_ALL}")
            else:
                self.stats["circuit_breaks"] += 1
                return self._handle_circuit_open(prompt)
        
        # 尝试从缓存获取
        if use_cache and self.enable_cache:
            cached = self._get_from_cache(prompt)
            if cached:
                self.stats["cache_hits"] += 1
                self.stats["successful_requests"] += 1
                return {
                    "success": True,
                    "content": cached,
                    "source": "cache",
                    "attempts": 0,
                    "error": None
                }
        
        # 尝试 API 调用（带重试）
        for attempt in range(self.max_retries):
            try:
                result = self._call_api(prompt, attempt)
                
                # 成功
                self._on_success()
                self._cache_response(prompt, result)
                self.stats["successful_requests"] += 1
                
                return {
                    "success": True,
                    "content": result,
                    "source": "api",
                    "attempts": attempt + 1,
                    "error": None
                }
                
            except Exception as e:
                self.stats["retries"] += 1
                
                # 最后一次尝试失败
                if attempt == self.max_retries - 1:
                    self._on_failure()
                    self.stats["failed_requests"] += 1
                    
                    # 尝试降级
                    if self.enable_fallback:
                        return self._handle_fallback(prompt, str(e))
                    
                    return {
                        "success": False,
                        "content": None,
                        "source": "none",
                        "attempts": attempt + 1,
                        "error": str(e)
                    }
                
                # 计算延迟（指数退避 + 抖动）
                delay = self._calculate_delay(attempt)
                print(f"{Fore.YELLOW}⚠️  尝试 {attempt + 1} 失败: {e}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}等待 {delay:.2f} 秒后重试...{Style.RESET_ALL}")
                time.sleep(delay)
    
    def _call_api(self, prompt: str, attempt: int) -> str:
        """调用 API"""
        print(f"{Fore.CYAN}[尝试 {attempt + 1}/{self.max_retries}] 调用 API...{Style.RESET_ALL}")
        
        response = requests.post(
            f"{self.api_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        elif response.status_code in [429, 500, 502, 503, 504]:
            raise Exception(f"Retryable error: {response.status_code}")
        else:
            raise Exception(f"Non-retryable error: {response.status_code}")
    
    def _calculate_delay(self, attempt: int) -> float:
        """计算延迟时间（指数退避 + 抖动）"""
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        # 添加抖动
        delay = delay * (0.5 + random.random())
        return delay
    
    def _on_success(self):
        """成功回调"""
        if self.circuit_state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.circuit_state = CircuitState.CLOSED
                self.failure_count = 0
                print(f"{Fore.GREEN}🔓 断路器: HALF_OPEN → CLOSED{Style.RESET_ALL}")
        else:
            self.failure_count = 0
    
    def _on_failure(self):
        """失败回调"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.circuit_state == CircuitState.HALF_OPEN:
            self.circuit_state = CircuitState.OPEN
            print(f"{Fore.RED}🔒 断路器: HALF_OPEN → OPEN{Style.RESET_ALL}")
        elif self.circuit_state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.circuit_state = CircuitState.OPEN
                print(f"{Fore.RED}🔒 断路器: CLOSED → OPEN{Style.RESET_ALL}")
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置断路器"""
        if self.last_failure_time is None:
            return False
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.circuit_timeout
    
    def _handle_circuit_open(self, prompt: str) -> Dict[str, Any]:
        """处理断路器打开的情况"""
        print(f"{Fore.RED}🔒 断路器打开，拒绝请求{Style.RESET_ALL}")
        
        # 尝试从缓存获取
        if self.enable_cache:
            cached = self._get_from_cache(prompt)
            if cached:
                self.stats["cache_hits"] += 1
                return {
                    "success": True,
                    "content": cached,
                    "source": "cache",
                    "attempts": 0,
                    "error": "Circuit breaker open, using cache"
                }
        
        # 返回默认响应
        return {
            "success": False,
            "content": "服务暂时不可用，请稍后再试。",
            "source": "default",
            "attempts": 0,
            "error": "Circuit breaker open"
        }
    
    def _handle_fallback(self, prompt: str, error: str) -> Dict[str, Any]:
        """处理降级"""
        print(f"{Fore.YELLOW}🔄 尝试降级方案...{Style.RESET_ALL}")
        self.stats["fallback_uses"] += 1
        
        # 降级方案 1: 从缓存获取
        if self.enable_cache:
            cached = self._get_from_cache(prompt)
            if cached:
                print(f"{Fore.GREEN}✓ 使用缓存{Style.RESET_ALL}")
                return {
                    "success": True,
                    "content": cached,
                    "source": "cache",
                    "attempts": self.max_retries,
                    "error": error
                }
        
        # 降级方案 2: 返回默认响应
        print(f"{Fore.YELLOW}⚠️  返回默认响应{Style.RESET_ALL}")
        return {
            "success": False,
            "content": "抱歉，服务暂时不可用，请稍后再试。",
            "source": "default",
            "attempts": self.max_retries,
            "error": error
        }
    
    def _get_from_cache(self, prompt: str) -> Optional[str]:
        """从缓存获取"""
        return self.cache.get(prompt)
    
    def _cache_response(self, prompt: str, response: str):
        """缓存响应"""
        self.cache[prompt] = response
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.stats["total_requests"]
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            "success_rate": f"{self.stats['successful_requests'] / total * 100:.1f}%",
            "failure_rate": f"{self.stats['failed_requests'] / total * 100:.1f}%",
            "avg_retries": f"{self.stats['retries'] / total:.2f}",
            "cache_hit_rate": f"{self.stats['cache_hits'] / total * 100:.1f}%"
        }


def demo_production_client():
    """演示生产级客户端"""
    print(f"{Fore.CYAN}{'='*60}")
    print("生产级 LLM 客户端演示")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 创建客户端
    client = ProductionLLMClient(
        api_base_url=API_BASE_URL,
        api_key=API_KEY,
        model_id=MODEL_ID,
        max_retries=3,
        failure_threshold=3,
        circuit_timeout=5.0
    )
    
    # 测试用例
    test_cases = [
        "1+1=?",
        "Python 是什么？",
        "说个笑话",
        "1+1=?",  # 重复，会命中缓存
        "推荐一本书",
    ]
    
    for i, prompt in enumerate(test_cases, 1):
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"测试 {i}: {prompt}")
        print(f"{'='*60}{Style.RESET_ALL}\n")
        
        result = client.chat(prompt)
        
        if result["success"]:
            print(f"\n{Fore.GREEN}✓ 成功{Style.RESET_ALL}")
            print(f"  内容: {result['content'][:100]}...")
            print(f"  来源: {result['source']}")
            print(f"  尝试次数: {result['attempts']}")
        else:
            print(f"\n{Fore.RED}✗ 失败{Style.RESET_ALL}")
            print(f"  错误: {result['error']}")
            print(f"  来源: {result['source']}")
        
        time.sleep(1)
    
    # 显示统计
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("统计信息")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    stats = client.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("生产级错误处理示例")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}集成特性:{Style.RESET_ALL}")
    print("  ✅ 指数退避重试")
    print("  ✅ 断路器保护")
    print("  ✅ 多级降级")
    print("  ✅ 缓存支持")
    print("  ✅ 监控统计")
    print("  ✅ 日志记录\n")
    
    demo_production_client()
    
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("生产环境建议")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}1. 监控和报警:{Style.RESET_ALL}")
    print("  - 监控成功率、失败率")
    print("  - 监控重试率、断路器状态")
    print("  - 设置报警阈值\n")
    
    print(f"{Fore.YELLOW}2. 日志记录:{Style.RESET_ALL}")
    print("  - 记录所有错误和重试")
    print("  - 记录断路器状态变化")
    print("  - 记录降级使用情况\n")
    
    print(f"{Fore.YELLOW}3. 配置管理:{Style.RESET_ALL}")
    print("  - 使用配置文件或环境变量")
    print("  - 支持动态调整参数")
    print("  - 不同环境使用不同配置\n")
    
    print(f"{Fore.YELLOW}4. 测试:{Style.RESET_ALL}")
    print("  - 单元测试各个组件")
    print("  - 集成测试完整流程")
    print("  - 混沌测试（故意注入失败）\n")
    
    print(f"{Fore.GREEN}推荐工具:{Style.RESET_ALL}")
    print("  - tenacity: 重试库")
    print("  - pybreaker: 断路器库")
    print("  - prometheus: 监控")
    print("  - sentry: 错误追踪\n")


if __name__ == "__main__":
    main()
