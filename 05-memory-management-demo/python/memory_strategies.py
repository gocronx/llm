"""
对话记忆管理策略演示
展示不同的记忆管理方法及其优缺点
"""

import os
import json
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


def call_llm(messages: List[Dict[str, str]], max_tokens: int = 150) -> str:
    """调用 LLM"""
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL_ID,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7
        },
        timeout=60
    )
    
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"错误: {response.status_code}"


def estimate_tokens(text: str) -> int:
    """估算 token 数量（简化版：中文约 1.5 字符/token，英文约 4 字符/token）"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def print_memory_info(messages: List[Dict[str, str]], strategy_name: str):
    """显示记忆信息"""
    total_text = " ".join(m["content"] for m in messages)
    tokens = estimate_tokens(total_text)
    print(f"\n{Fore.CYAN}[{strategy_name}] 记忆状态{Style.RESET_ALL}")
    print(f"  消息数量: {len(messages)}")
    print(f"  估算 Token: {tokens}")
    print(f"  成本估算: ~${tokens * 0.00001:.6f} (假设 $0.01/1K tokens)")


# ============================================================
# 策略 1: 完整记忆（Full Memory）
# ============================================================

class FullMemoryChat:
    """完整记忆：保存所有对话历史"""
    
    def __init__(self):
        self.messages = []
        self.system_prompt = {
            "role": "system",
            "content": "你是一个友好的助手。用简短的1-2句话回答问题。"
        }
    
    def chat(self, user_input: str) -> str:
        """发送消息并获取回复"""
        # 添加用户消息
        self.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # 构建请求消息（system + 所有历史）
        request_messages = [self.system_prompt] + self.messages
        
        # 调用 LLM
        response = call_llm(request_messages)
        
        # 保存助手回复
        self.messages.append({
            "role": "assistant",
            "content": response
        })
        
        return response
    
    def get_memory_info(self):
        """获取记忆信息"""
        print_memory_info([self.system_prompt] + self.messages, "完整记忆")


# ============================================================
# 策略 2: 滑动窗口（Sliding Window）
# ============================================================

class SlidingWindowChat:
    """滑动窗口：只保留最近 N 条消息"""
    
    def __init__(self, window_size: int = 10):
        self.messages = []
        self.window_size = window_size  # 保留最近 N 条消息
        self.system_prompt = {
            "role": "system",
            "content": "你是一个友好的助手。用简短的1-2句话回答问题。"
        }
    
    def chat(self, user_input: str) -> str:
        """发送消息并获取回复"""
        # 添加用户消息
        self.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # 只保留最近的消息
        if len(self.messages) > self.window_size:
            self.messages = self.messages[-self.window_size:]
        
        # 构建请求消息（system + 窗口内的消息）
        request_messages = [self.system_prompt] + self.messages
        
        # 调用 LLM
        response = call_llm(request_messages)
        
        # 保存助手回复
        self.messages.append({
            "role": "assistant",
            "content": response
        })
        
        # 再次检查窗口大小
        if len(self.messages) > self.window_size:
            self.messages = self.messages[-self.window_size:]
        
        return response
    
    def get_memory_info(self):
        """获取记忆信息"""
        print_memory_info([self.system_prompt] + self.messages, "滑动窗口")
        print(f"  窗口大小: {self.window_size}")


# ============================================================
# 策略 3: 摘要记忆（Summary Memory）
# ============================================================

class SummaryMemoryChat:
    """摘要记忆：定期总结历史对话"""
    
    def __init__(self, summary_threshold: int = 6):
        self.messages = []
        self.summary = ""
        self.summary_threshold = summary_threshold
        self.system_prompt = {
            "role": "system",
            "content": "你是一个友好的助手。用简短的1-2句话回答问题。"
        }
    
    def chat(self, user_input: str) -> str:
        """发送消息并获取回复"""
        # 添加用户消息
        self.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # 检查是否需要生成摘要
        if len(self.messages) >= self.summary_threshold:
            self._generate_summary()
        
        # 构建请求消息
        request_messages = [self.system_prompt]
        if self.summary:
            request_messages.append({
                "role": "system",
                "content": f"用户信息：{self.summary}"
            })
        request_messages.extend(self.messages)
        
        # 调用 LLM
        response = call_llm(request_messages)
        
        # 保存助手回复
        self.messages.append({
            "role": "assistant",
            "content": response
        })
        
        return response
    
    def _generate_summary(self):
        """生成对话摘要"""
        print(f"\n{Fore.YELLOW}📝 生成对话摘要...{Style.RESET_ALL}")
        
        # 提取关键信息
        conversation_text = "\n".join([
            f"{m['role']}: {m['content']}" for m in self.messages
        ])
        
        # 构建更结构化的摘要请求
        summary_messages = [
            {
                "role": "system",
                "content": "你是一个信息提取助手。提取对话中的关键事实信息。"
            },
            {
                "role": "user",
                "content": f"从以下对话中提取关键信息（姓名、年龄、爱好等），用简短的列表格式输出：\n\n{conversation_text}"
            }
        ]
        
        # 生成摘要
        self.summary = call_llm(summary_messages, max_tokens=150)
        print(f"{Fore.GREEN}✓ 摘要生成完成{Style.RESET_ALL}")
        print(f"  摘要: {self.summary[:100]}...")
        
        # 清空详细历史，只保留摘要
        self.messages = []
    
    def get_memory_info(self):
        """获取记忆信息"""
        all_messages = [self.system_prompt]
        if self.summary:
            all_messages.append({
                "role": "system",
                "content": f"用户信息: {self.summary}"
            })
        all_messages.extend(self.messages)
        print_memory_info(all_messages, "摘要记忆")
        print(f"  摘要阈值: {self.summary_threshold}")
        if self.summary:
            print(f"  当前摘要: {self.summary[:50]}...")


# ============================================================
# 策略 4: Token 限制记忆（Token-Limited Memory）
# ============================================================

class TokenLimitedChat:
    """Token 限制：根据 Token 数量动态调整历史"""
    
    def __init__(self, max_tokens: int = 500):
        self.messages = []
        self.max_tokens = max_tokens
        self.system_prompt = {
            "role": "system",
            "content": "你是一个友好的助手。用简短的1-2句话回答问题。"
        }
    
    def chat(self, user_input: str) -> str:
        """发送消息并获取回复"""
        # 添加用户消息
        self.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # 根据 Token 限制裁剪历史
        self._trim_by_tokens()
        
        # 构建请求消息（system + 历史消息）
        request_messages = [self.system_prompt] + self.messages
        
        # 调用 LLM
        response = call_llm(request_messages)
        
        # 保存助手回复
        self.messages.append({
            "role": "assistant",
            "content": response
        })
        
        # 再次裁剪
        self._trim_by_tokens()
        
        return response
    
    def _trim_by_tokens(self):
        """根据 Token 数量裁剪历史"""
        while len(self.messages) > 2:  # 至少保留 2 条
            # 计算总 token（包括 system prompt）
            total_text = self.system_prompt["content"] + " " + " ".join(m["content"] for m in self.messages)
            tokens = estimate_tokens(total_text)
            
            if tokens <= self.max_tokens:
                break
            
            # 删除最早的消息（保留最近的）
            self.messages.pop(0)
    
    def get_memory_info(self):
        """获取记忆信息"""
        print_memory_info([self.system_prompt] + self.messages, "Token 限制")
        print(f"  Token 限制: {self.max_tokens}")


# ============================================================
# 主演示
# ============================================================

def demo_strategy(strategy_class, strategy_name: str, conversations: List[str]):
    """演示某个策略"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{strategy_name}")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    chat = strategy_class()
    
    for i, user_input in enumerate(conversations, 1):
        print(f"\n{Fore.GREEN}[轮次 {i}] 用户:{Style.RESET_ALL} {user_input}")
        response = chat.chat(user_input)
        print(f"{Fore.BLUE}助手:{Style.RESET_ALL} {response[:150]}{'...' if len(response) > 150 else ''}")
        
        # 显示记忆状态
        chat.get_memory_info()


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("对话记忆管理策略演示")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 测试对话
    conversations = [
        "你好，我叫张三",
        "我今年 25 岁",
        "我喜欢编程",
        "我刚才说我叫什么名字？",
        "我多大了？",
        "我有什么爱好？"
    ]
    
    print(f"{Fore.YELLOW}测试对话序列:{Style.RESET_ALL}")
    for i, conv in enumerate(conversations, 1):
        print(f"  {i}. {conv}")
    
    # 策略 1: 完整记忆
    demo_strategy(FullMemoryChat, "策略 1: 完整记忆（Full Memory）", conversations)
    
    # 策略 2: 滑动窗口
    demo_strategy(
        lambda: SlidingWindowChat(window_size=4),
        "策略 2: 滑动窗口（Sliding Window, 窗口=4）",
        conversations
    )
    
    # 策略 3: 摘要记忆
    demo_strategy(
        lambda: SummaryMemoryChat(summary_threshold=4),
        "策略 3: 摘要记忆（Summary Memory, 阈值=4）",
        conversations
    )
    
    # 策略 4: Token 限制
    demo_strategy(
        lambda: TokenLimitedChat(max_tokens=300),
        "策略 4: Token 限制（Token-Limited, 限制=300）",
        conversations
    )
    
    # 总结
    print(f"\n{Fore.CYAN}{'='*60}")
    print("策略对比总结")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}1. 完整记忆{Style.RESET_ALL}")
    print("  ✅ 优点: 记住所有信息，上下文完整")
    print("  ❌ 缺点: Token 消耗大，成本高，可能超出上下文限制")
    print("  📌 适用: 短对话、重要对话\n")
    
    print(f"{Fore.YELLOW}2. 滑动窗口{Style.RESET_ALL}")
    print("  ✅ 优点: Token 可控，实现简单")
    print("  ❌ 缺点: 会忘记早期信息")
    print("  📌 适用: 一般对话、成本敏感场景\n")
    
    print(f"{Fore.YELLOW}3. 摘要记忆{Style.RESET_ALL}")
    print("  ✅ 优点: 保留关键信息，Token 可控")
    print("  ❌ 缺点: 摘要可能丢失细节，需要额外 LLM 调用")
    print("  📌 适用: 长对话、需要保留关键信息\n")
    
    print(f"{Fore.YELLOW}4. Token 限制{Style.RESET_ALL}")
    print("  ✅ 优点: 精确控制成本")
    print("  ❌ 缺点: 可能在对话中途突然’失忆‘")
    print("  📌 适用: 严格成本控制场景\n")
    
    print(f"{Fore.GREEN}建议:{Style.RESET_ALL}")
    print("  - 短对话（<10 轮）：完整记忆")
    print("  - 一般对话（10-50 轮）：滑动窗口")
    print("  - 长对话（>50 轮）：摘要记忆")
    print("  - 成本敏感：Token 限制\n")


if __name__ == "__main__":
    main()
