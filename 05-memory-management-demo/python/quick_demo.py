"""
快速演示 - 展示核心概念
"""

import os
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv("../.env")

print(f"{Fore.CYAN}{'='*60}")
print("对话记忆管理 - 快速演示")
print(f"{'='*60}{Style.RESET_ALL}\n")

print(f"{Fore.YELLOW}核心概念:{Style.RESET_ALL}\n")

print("1. LLM 本身没有记忆")
print("   每次调用都是独立的\n")

print("2. 记忆管理 = 每次都把历史发送给 LLM")
print("   messages = [历史消息1, 历史消息2, ..., 新消息]\n")

print("3. 四种策略:")
print("   - 完整记忆: 保存所有历史（Token 多，成本高）")
print("   - 滑动窗口: 只保留最近 N 条（Token 可控）")
print("   - 摘要记忆: 定期总结历史（保留关键信息）")
print("   - Token 限制: 根据 Token 数量裁剪（精确控制成本）\n")

print(f"{Fore.CYAN}{'='*60}")
print("示例：滑动窗口策略")
print(f"{'='*60}{Style.RESET_ALL}\n")

class SimpleChat:
    def __init__(self, window_size=4):
        self.messages = []
        self.window_size = window_size
    
    def chat(self, user_input):
        # 添加用户消息
        self.messages.append({"role": "user", "content": user_input})
        
        # 保持窗口大小
        if len(self.messages) > self.window_size:
            removed = self.messages.pop(0)
            print(f"  {Fore.RED}🗑️  删除最早的消息: {removed['content'][:30]}...{Style.RESET_ALL}")
        
        # 模拟 LLM 回复
        response = f"收到: {user_input}"
        self.messages.append({"role": "assistant", "content": response})
        
        if len(self.messages) > self.window_size:
            removed = self.messages.pop(0)
            print(f"  {Fore.RED}🗑️  删除最早的消息: {removed['content'][:30]}...{Style.RESET_ALL}")
        
        return response
    
    def show_memory(self):
        print(f"\n  {Fore.CYAN}当前记忆 ({len(self.messages)}/{self.window_size}):{Style.RESET_ALL}")
        for msg in self.messages:
            role_icon = "👤" if msg["role"] == "user" else "🤖"
            print(f"    {role_icon} {msg['content'][:40]}...")

# 演示
chat = SimpleChat(window_size=4)

conversations = [
    "你好，我叫张三",
    "我今年 25 岁",
    "我喜欢编程",
    "我刚才说我叫什么名字？"
]

for i, user_input in enumerate(conversations, 1):
    print(f"\n{Fore.GREEN}[轮次 {i}] 用户:{Style.RESET_ALL} {user_input}")
    response = chat.chat(user_input)
    chat.show_memory()

print(f"\n\n{Fore.YELLOW}💡 观察:{Style.RESET_ALL}")
print("  - 窗口大小 = 4，所以最多保留 4 条消息")
print("  - 当超过 4 条时，自动删除最早的消息")
print("  - 第 4 轮时，已经忘记了第 1 轮的'我叫张三'\n")

print(f"{Fore.GREEN}完整演示请运行:{Style.RESET_ALL}")
print("  python memory_strategies.py    # 四种策略对比")
print("  python persistent_memory.py    # 持久化演示")
print("  python token_management.py     # Token 和成本管理\n")
