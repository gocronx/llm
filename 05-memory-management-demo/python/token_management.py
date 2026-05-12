"""
Token 计数和成本管理演示
展示如何精确计算 Token 和估算成本
"""

import os
import requests
from typing import List, Dict
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


def estimate_tokens_simple(text: str) -> int:
    """简单估算（不准确，但快速）"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def estimate_tokens_accurate(text: str) -> int:
    """更准确的估算（使用 tiktoken）"""
    try:
        import tiktoken
        # 使用 cl100k_base 编码（GPT-4、GPT-3.5-turbo 使用）
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except ImportError:
        print(f"{Fore.YELLOW}⚠️  tiktoken 未安装，使用简单估算{Style.RESET_ALL}")
        return estimate_tokens_simple(text)


class TokenAwareChat:
    """Token 感知的对话系统"""
    
    def __init__(self, max_tokens: int = 2000, pricing: Dict[str, float] = None):
        self.messages = []
        self.max_tokens = max_tokens
        self.pricing = pricing or {
            "input": 0.01 / 1000,   # $0.01 per 1K input tokens
            "output": 0.03 / 1000   # $0.03 per 1K output tokens
        }
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
    
    def chat(self, user_input: str) -> str:
        """发送消息并获取回复"""
        # 添加用户消息
        self.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # 计算当前 Token
        current_tokens = self._count_tokens()
        
        # 检查是否超出限制
        if current_tokens > self.max_tokens:
            print(f"{Fore.RED}⚠️  Token 超出限制 ({current_tokens}/{self.max_tokens})，自动裁剪{Style.RESET_ALL}")
            self._trim_messages()
            current_tokens = self._count_tokens()
        
        # 调用 LLM
        response = requests.post(
            f"{API_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL_ID,
                "messages": self.messages,
                "max_tokens": 200,
                "temperature": 0.7
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            assistant_message = result["choices"][0]["message"]["content"]
            
            # 记录 Token 使用（如果 API 返回）
            if "usage" in result:
                input_tokens = result["usage"].get("prompt_tokens", 0)
                output_tokens = result["usage"].get("completion_tokens", 0)
            else:
                # 估算
                input_tokens = current_tokens
                output_tokens = estimate_tokens_accurate(assistant_message)
            
            # 更新统计
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cost += (
                input_tokens * self.pricing["input"] +
                output_tokens * self.pricing["output"]
            )
        else:
            assistant_message = f"错误: {response.status_code}"
            input_tokens = 0
            output_tokens = 0
        
        # 保存助手回复
        self.messages.append({
            "role": "assistant",
            "content": assistant_message
        })
        
        # 显示 Token 信息
        self._print_token_info(input_tokens, output_tokens)
        
        return assistant_message
    
    def _count_tokens(self) -> int:
        """计算当前对话的 Token 数"""
        total_text = " ".join(m["content"] for m in self.messages)
        return estimate_tokens_accurate(total_text)
    
    def _trim_messages(self):
        """裁剪消息以符合 Token 限制"""
        while len(self.messages) > 2 and self._count_tokens() > self.max_tokens:
            # 删除最早的消息（保留最近的）
            self.messages.pop(0)
    
    def _print_token_info(self, input_tokens: int, output_tokens: int):
        """显示 Token 信息"""
        print(f"\n{Fore.CYAN}📊 Token 使用情况{Style.RESET_ALL}")
        print(f"  本次输入: {input_tokens} tokens")
        print(f"  本次输出: {output_tokens} tokens")
        print(f"  本次成本: ${input_tokens * self.pricing['input'] + output_tokens * self.pricing['output']:.6f}")
        print(f"  累计输入: {self.total_input_tokens} tokens")
        print(f"  累计输出: {self.total_output_tokens} tokens")
        print(f"  累计成本: ${self.total_cost:.6f}")
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost": self.total_cost,
            "message_count": len(self.messages),
            "avg_tokens_per_message": (self.total_input_tokens + self.total_output_tokens) / max(len(self.messages), 1)
        }


def demo_token_counting():
    """演示 Token 计数"""
    print(f"{Fore.CYAN}{'='*60}")
    print("演示 1: Token 计数对比")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    test_texts = [
        "Hello, world!",
        "你好，世界！",
        "This is a longer sentence with more words to demonstrate token counting.",
        "这是一个更长的句子，用来演示 Token 计数的准确性。",
        "混合 mixed 中英文 English text 测试 test。"
    ]
    
    print(f"{'文本':<50} {'简单估算':<12} {'准确计数':<12} {'差异':<10}")
    print("-" * 84)
    
    for text in test_texts:
        simple = estimate_tokens_simple(text)
        accurate = estimate_tokens_accurate(text)
        diff = abs(simple - accurate)
        diff_pct = (diff / accurate * 100) if accurate > 0 else 0
        
        display_text = text if len(text) <= 47 else text[:44] + "..."
        print(f"{display_text:<50} {simple:<12} {accurate:<12} {diff} ({diff_pct:.1f}%)")


def demo_cost_management():
    """演示成本管理"""
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("演示 2: 成本管理")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 创建 Token 感知的对话
    chat = TokenAwareChat(max_tokens=500)
    
    conversations = [
        "你好，请介绍一下你自己",
        "你能做什么？",
        "给我讲个笑话"
    ]
    
    for i, user_input in enumerate(conversations, 1):
        print(f"\n{Fore.GREEN}[轮次 {i}] 用户:{Style.RESET_ALL} {user_input}")
        response = chat.chat(user_input)
        print(f"{Fore.BLUE}助手:{Style.RESET_ALL} {response[:100]}{'...' if len(response) > 100 else ''}")
    
    # 显示最终统计
    print(f"\n{Fore.CYAN}{'='*60}")
    print("最终统计")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    stats = chat.get_statistics()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")


def demo_pricing_comparison():
    """演示不同模型的定价对比"""
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("演示 3: 不同模型定价对比")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 假设的定价（每 1K tokens）
    models = {
        "GPT-4": {"input": 0.03, "output": 0.06},
        "GPT-3.5-turbo": {"input": 0.001, "output": 0.002},
        "Claude-3-Opus": {"input": 0.015, "output": 0.075},
        "Claude-3-Sonnet": {"input": 0.003, "output": 0.015},
        "本地模型": {"input": 0.0, "output": 0.0}
    }
    
    # 假设场景：1000 次对话，每次 500 input tokens + 200 output tokens
    total_input = 1000 * 500
    total_output = 1000 * 200
    
    print(f"场景: 1000 次对话")
    print(f"  每次输入: 500 tokens")
    print(f"  每次输出: 200 tokens")
    print(f"  总输入: {total_input:,} tokens")
    print(f"  总输出: {total_output:,} tokens\n")
    
    print(f"{'模型':<20} {'输入成本':<15} {'输出成本':<15} {'总成本':<15}")
    print("-" * 65)
    
    for model, pricing in models.items():
        input_cost = (total_input / 1000) * pricing["input"]
        output_cost = (total_output / 1000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        print(f"{model:<20} ${input_cost:<14.2f} ${output_cost:<14.2f} ${total_cost:<14.2f}")
    
    print(f"\n{Fore.YELLOW}💡 提示:{Style.RESET_ALL}")
    print("  - 本地模型虽然免费，但需要考虑硬件成本和维护成本")
    print("  - 云端模型按使用付费，适合不确定的负载")
    print("  - 选择模型时要平衡成本和质量")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("Token 计数和成本管理演示")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 演示 1: Token 计数
    demo_token_counting()
    
    # 演示 2: 成本管理
    demo_cost_management()
    
    # 演示 3: 定价对比
    demo_pricing_comparison()
    
    # 总结
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("Token 管理最佳实践")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}1. 准确计数{Style.RESET_ALL}")
    print("  - 使用 tiktoken 库进行准确计数")
    print("  - 不同模型使用不同的编码方式")
    print("  - 定期校准估算公式\n")
    
    print(f"{Fore.YELLOW}2. 成本控制{Style.RESET_ALL}")
    print("  - 设置 Token 上限")
    print("  - 使用滑动窗口或摘要")
    print("  - 监控和报警\n")
    
    print(f"{Fore.YELLOW}3. 优化策略{Style.RESET_ALL}")
    print("  - 简化 System Prompt")
    print("  - 压缩历史对话")
    print("  - 使用更便宜的模型处理简单任务\n")
    
    print(f"{Fore.GREEN}建议:{Style.RESET_ALL}")
    print("  - 开发阶段：使用本地模型或便宜的模型")
    print("  - 生产环境：根据任务复杂度选择模型")
    print("  - 监控成本：设置预算和报警\n")


if __name__ == "__main__":
    main()
