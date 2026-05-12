"""
断路器演示
展示断路器模式：防止级联失败，快速失败
"""

import os
import time
import requests
from enum import Enum
from typing import Optional, Callable
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
    CLOSED = "closed"      # 关闭（正常工作）
    OPEN = "open"          # 打开（拒绝请求）
    HALF_OPEN = "half_open"  # 半开（尝试恢复）


class CircuitBreaker:
    """
    断路器实现
    
    工作原理:
    1. CLOSED（关闭）: 正常工作，记录失败次数
    2. OPEN（打开）: 失败次数超过阈值，拒绝所有请求
    3. HALF_OPEN（半开）: 超时后尝试恢复，允许少量请求测试
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,      # 失败阈值
        timeout: float = 60.0,           # 打开状态持续时间（秒）
        success_threshold: int = 2       # 半开状态成功阈值
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change: datetime = datetime.now()
    
    def call(self, func: Callable, *args, **kwargs):
        """
        通过断路器调用函数
        
        返回: (success: bool, result: any, error: Exception)
        """
        # 检查是否应该从 OPEN 转到 HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                print(f"{Fore.YELLOW}🔄 断路器从 OPEN 转到 HALF_OPEN（尝试恢复）{Style.RESET_ALL}")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                # 仍在打开状态，快速失败
                remaining = self.timeout - (datetime.now() - self.last_failure_time).total_seconds()
                raise Exception(f"断路器打开，拒绝请求（{remaining:.1f} 秒后重试）")
        
        # 尝试调用函数
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return True, result, None
        except Exception as e:
            self._on_failure()
            return False, None, e
    
    def _on_success(self):
        """成功回调"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            print(f"{Fore.GREEN}✓ 半开状态成功 ({self.success_count}/{self.success_threshold}){Style.RESET_ALL}")
            
            if self.success_count >= self.success_threshold:
                print(f"{Fore.GREEN}🔓 断路器从 HALF_OPEN 转到 CLOSED（恢复正常）{Style.RESET_ALL}")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.last_state_change = datetime.now()
        else:
            # CLOSED 状态，重置失败计数
            self.failure_count = 0
    
    def _on_failure(self):
        """失败回调"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            print(f"{Fore.RED}✗ 半开状态失败，重新打开断路器{Style.RESET_ALL}")
            self.state = CircuitState.OPEN
            self.last_state_change = datetime.now()
        elif self.state == CircuitState.CLOSED:
            print(f"{Fore.YELLOW}⚠️  失败 ({self.failure_count}/{self.failure_threshold}){Style.RESET_ALL}")
            
            if self.failure_count >= self.failure_threshold:
                print(f"{Fore.RED}🔒 断路器从 CLOSED 转到 OPEN（停止请求）{Style.RESET_ALL}")
                self.state = CircuitState.OPEN
                self.last_state_change = datetime.now()
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置"""
        if self.last_failure_time is None:
            return False
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.timeout
    
    def get_state(self) -> dict:
        """获取断路器状态"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "time_since_last_failure": (datetime.now() - self.last_failure_time).total_seconds() if self.last_failure_time else None
        }


def call_llm(prompt: str) -> str:
    """LLM 调用（可能失败）"""
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 50
        },
        timeout=30
    )
    
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"API Error {response.status_code}")


def demo_circuit_breaker_states():
    """演示断路器状态转换"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 1: 断路器状态转换")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}状态说明:{Style.RESET_ALL}")
    print("  🟢 CLOSED（关闭）: 正常工作，允许所有请求")
    print("  🔴 OPEN（打开）: 停止请求，快速失败")
    print("  🟡 HALF_OPEN（半开）: 尝试恢复，允许少量请求测试\n")
    
    print(f"{Fore.YELLOW}状态转换:{Style.RESET_ALL}")
    print("  CLOSED → OPEN: 失败次数超过阈值")
    print("  OPEN → HALF_OPEN: 超时后尝试恢复")
    print("  HALF_OPEN → CLOSED: 成功次数达到阈值")
    print("  HALF_OPEN → OPEN: 再次失败\n")


def demo_basic_circuit_breaker():
    """基础断路器演示"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 2: 基础断路器")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 创建断路器（低阈值便于演示）
    breaker = CircuitBreaker(
        failure_threshold=3,  # 3 次失败后打开
        timeout=5.0,          # 5 秒后尝试恢复
        success_threshold=2   # 2 次成功后关闭
    )
    
    test_cases = [
        ("正常请求 1", "1+1=?", False),
        ("正常请求 2", "2+2=?", False),
        ("正常请求 3", "3+3=?", False),
        ("失败请求 1", "模拟失败" * 1000, True),  # 超长请求可能失败
        ("失败请求 2", "模拟失败" * 1000, True),
        ("失败请求 3", "模拟失败" * 1000, True),  # 这次会触发断路器打开
        ("被拒绝请求", "4+4=?", False),  # 断路器打开，直接拒绝
    ]
    
    for i, (name, prompt, expect_fail) in enumerate(test_cases, 1):
        print(f"\n{Fore.CYAN}[测试 {i}] {name}{Style.RESET_ALL}")
        print(f"状态: {breaker.state.value.upper()}")
        
        try:
            success, result, error = breaker.call(call_llm, prompt[:50])
            if success:
                print(f"{Fore.GREEN}✓ 成功: {result[:50]}...{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}✗ 失败: {error}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}✗ 断路器拒绝: {e}{Style.RESET_ALL}")
        
        time.sleep(0.5)  # 短暂延迟


def demo_circuit_breaker_recovery():
    """演示断路器恢复"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 3: 断路器恢复")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    breaker = CircuitBreaker(
        failure_threshold=2,
        timeout=3.0,  # 3 秒后尝试恢复
        success_threshold=2
    )
    
    print(f"{Fore.YELLOW}步骤 1: 触发断路器打开{Style.RESET_ALL}\n")
    
    # 触发失败
    for i in range(3):
        try:
            breaker.call(call_llm, "模拟失败" * 1000)
        except:
            pass
        time.sleep(0.5)
    
    print(f"\n{Fore.YELLOW}步骤 2: 等待超时（3 秒）{Style.RESET_ALL}\n")
    time.sleep(3.5)
    
    print(f"{Fore.YELLOW}步骤 3: 尝试恢复（HALF_OPEN）{Style.RESET_ALL}\n")
    
    # 尝试恢复
    for i in range(3):
        print(f"\n尝试 {i+1}:")
        try:
            success, result, error = breaker.call(call_llm, f"{i+1}+{i+1}=?")
            if success:
                print(f"{Fore.GREEN}✓ 成功{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}✗ 失败{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}✗ 错误: {e}{Style.RESET_ALL}")
        
        time.sleep(0.5)


def demo_without_circuit_breaker():
    """对比：没有断路器的情况"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 4: 没有断路器 vs 有断路器")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.RED}❌ 没有断路器:{Style.RESET_ALL}")
    print("  - 持续尝试失败的请求")
    print("  - 浪费资源（CPU、网络、时间）")
    print("  - 可能导致级联失败")
    print("  - 用户体验差（长时间等待）\n")
    
    print(f"{Fore.GREEN}✅ 有断路器:{Style.RESET_ALL}")
    print("  - 快速失败，立即返回错误")
    print("  - 节省资源")
    print("  - 防止级联失败")
    print("  - 自动恢复机制")
    print("  - 更好的用户体验\n")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("断路器演示")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}核心概念:{Style.RESET_ALL}")
    print("1. 断路器：防止级联失败的保护机制")
    print("2. 快速失败：服务不可用时立即返回错误")
    print("3. 自动恢复：定期尝试恢复服务")
    print("4. 三种状态：CLOSED、OPEN、HALF_OPEN\n")
    
    # 演示 1: 状态说明
    demo_circuit_breaker_states()
    
    # 演示 2: 基础断路器
    demo_basic_circuit_breaker()
    
    # 演示 3: 恢复机制
    demo_circuit_breaker_recovery()
    
    # 演示 4: 对比
    demo_without_circuit_breaker()
    
    # 总结
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("最佳实践")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}推荐配置:{Style.RESET_ALL}")
    print("  - 失败阈值: 5-10 次")
    print("  - 超时时间: 30-60 秒")
    print("  - 成功阈值: 2-3 次\n")
    
    print(f"{Fore.YELLOW}适用场景:{Style.RESET_ALL}")
    print("  ✅ 调用外部 API")
    print("  ✅ 数据库连接")
    print("  ✅ 微服务调用")
    print("  ✅ 任何可能失败的远程调用\n")
    
    print(f"{Fore.GREEN}建议:{Style.RESET_ALL}")
    print("  - 结合重试机制使用")
    print("  - 监控断路器状态")
    print("  - 记录状态转换日志")
    print("  - 提供降级方案\n")


if __name__ == "__main__":
    main()
