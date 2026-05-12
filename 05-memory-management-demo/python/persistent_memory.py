"""
对话记忆持久化演示
展示如何保存和加载对话历史
"""

import os
import json
import requests
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


class PersistentChat:
    """支持持久化的对话系统"""
    
    def __init__(self, session_id: str = None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.messages = []
        self.metadata = {
            "session_id": self.session_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "message_count": 0
        }
    
    def chat(self, user_input: str) -> str:
        """发送消息并获取回复"""
        # 添加用户消息
        self.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat()
        })
        
        # 构建 API 请求消息（不包含 timestamp）
        api_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in self.messages
        ]
        
        # 调用 LLM
        response = requests.post(
            f"{API_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL_ID,
                "messages": api_messages,
                "max_tokens": 200,
                "temperature": 0.7
            },
            timeout=60
        )
        
        if response.status_code == 200:
            assistant_message = response.json()["choices"][0]["message"]["content"]
        else:
            assistant_message = f"错误: {response.status_code}"
        
        # 保存助手回复
        self.messages.append({
            "role": "assistant",
            "content": assistant_message,
            "timestamp": datetime.now().isoformat()
        })
        
        # 更新元数据
        self.metadata["updated_at"] = datetime.now().isoformat()
        self.metadata["message_count"] = len(self.messages)
        
        return assistant_message
    
    def save(self, filepath: str = None):
        """保存对话到文件"""
        if filepath is None:
            filepath = f"conversations/{self.session_id}.json"
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # 保存数据
        data = {
            "metadata": self.metadata,
            "messages": self.messages
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"{Fore.GREEN}✓ 对话已保存:{Style.RESET_ALL} {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'PersistentChat':
        """从文件加载对话"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        chat = cls(session_id=data["metadata"]["session_id"])
        chat.messages = data["messages"]
        chat.metadata = data["metadata"]
        
        print(f"{Fore.GREEN}✓ 对话已加载:{Style.RESET_ALL} {filepath}")
        print(f"  会话 ID: {chat.session_id}")
        print(f"  创建时间: {chat.metadata['created_at']}")
        print(f"  消息数量: {chat.metadata['message_count']}")
        
        return chat
    
    def export_markdown(self, filepath: str = None):
        """导出为 Markdown 格式"""
        if filepath is None:
            filepath = f"conversations/{self.session_id}.md"
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # 生成 Markdown
        lines = [
            f"# 对话记录",
            f"",
            f"**会话 ID:** {self.session_id}",
            f"**创建时间:** {self.metadata['created_at']}",
            f"**消息数量:** {self.metadata['message_count']}",
            f"",
            f"---",
            f""
        ]
        
        for i, msg in enumerate(self.messages, 1):
            role_name = "👤 用户" if msg["role"] == "user" else "🤖 助手"
            lines.append(f"## {i}. {role_name}")
            lines.append(f"")
            lines.append(f"**时间:** {msg.get('timestamp', 'N/A')}")
            lines.append(f"")
            lines.append(msg["content"])
            lines.append(f"")
            lines.append(f"---")
            lines.append(f"")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print(f"{Fore.GREEN}✓ Markdown 已导出:{Style.RESET_ALL} {filepath}")
    
    def get_summary(self) -> Dict[str, Any]:
        """获取对话摘要"""
        return {
            "session_id": self.session_id,
            "message_count": len(self.messages),
            "user_messages": sum(1 for m in self.messages if m["role"] == "user"),
            "assistant_messages": sum(1 for m in self.messages if m["role"] == "assistant"),
            "created_at": self.metadata["created_at"],
            "updated_at": self.metadata["updated_at"]
        }


def demo_save_and_load():
    """演示保存和加载"""
    print(f"{Fore.CYAN}{'='*60}")
    print("演示 1: 保存和加载对话")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 创建新对话
    print(f"{Fore.YELLOW}步骤 1: 创建新对话{Style.RESET_ALL}")
    chat1 = PersistentChat()
    print(f"  会话 ID: {chat1.session_id}\n")
    
    # 进行对话
    print(f"{Fore.YELLOW}步骤 2: 进行对话{Style.RESET_ALL}")
    conversations = [
        "你好，我叫李四",
        "我是一名程序员",
        "我喜欢 Python"
    ]
    
    for user_input in conversations:
        print(f"\n{Fore.GREEN}用户:{Style.RESET_ALL} {user_input}")
        response = chat1.chat(user_input)
        print(f"{Fore.BLUE}助手:{Style.RESET_ALL} {response[:100]}{'...' if len(response) > 100 else ''}")
    
    # 保存对话
    print(f"\n{Fore.YELLOW}步骤 3: 保存对话{Style.RESET_ALL}")
    chat1.save()
    
    # 导出 Markdown
    print(f"\n{Fore.YELLOW}步骤 4: 导出 Markdown{Style.RESET_ALL}")
    chat1.export_markdown()
    
    # 加载对话
    print(f"\n{Fore.YELLOW}步骤 5: 加载对话{Style.RESET_ALL}")
    filepath = f"conversations/{chat1.session_id}.json"
    chat2 = PersistentChat.load(filepath)
    
    # 继续对话
    print(f"\n{Fore.YELLOW}步骤 6: 继续对话{Style.RESET_ALL}")
    user_input = "我刚才说我叫什么名字？"
    print(f"\n{Fore.GREEN}用户:{Style.RESET_ALL} {user_input}")
    response = chat2.chat(user_input)
    print(f"{Fore.BLUE}助手:{Style.RESET_ALL} {response}")
    
    # 再次保存
    print(f"\n{Fore.YELLOW}步骤 7: 再次保存{Style.RESET_ALL}")
    chat2.save()
    
    # 显示摘要
    print(f"\n{Fore.YELLOW}步骤 8: 对话摘要{Style.RESET_ALL}")
    summary = chat2.get_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")


def demo_multiple_sessions():
    """演示多会话管理"""
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("演示 2: 多会话管理")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 创建多个会话
    sessions = []
    
    print(f"{Fore.YELLOW}创建 3 个会话{Style.RESET_ALL}\n")
    for i in range(3):
        chat = PersistentChat()
        chat.chat(f"你好，我是用户 {i+1}")
        chat.save()
        sessions.append(chat.session_id)
        print(f"  会话 {i+1}: {chat.session_id}")
    
    # 列出所有会话
    print(f"\n{Fore.YELLOW}列出所有会话{Style.RESET_ALL}\n")
    conversations_dir = "conversations"
    if os.path.exists(conversations_dir):
        files = [f for f in os.listdir(conversations_dir) if f.endswith('.json')]
        print(f"  找到 {len(files)} 个会话文件:")
        for f in files:
            filepath = os.path.join(conversations_dir, f)
            with open(filepath, 'r') as file:
                data = json.load(file)
                print(f"    - {f}: {data['metadata']['message_count']} 条消息")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("对话记忆持久化演示")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 演示 1: 保存和加载
    demo_save_and_load()
    
    # 演示 2: 多会话管理
    demo_multiple_sessions()
    
    # 总结
    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("持久化的价值")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}为什么需要持久化？{Style.RESET_ALL}")
    print("  1. 用户可以随时中断和恢复对话")
    print("  2. 可以分析历史对话，改进系统")
    print("  3. 可以导出对话记录，用于审计")
    print("  4. 可以在多个设备间同步对话\n")
    
    print(f"{Fore.YELLOW}持久化方式对比{Style.RESET_ALL}")
    print("  1. JSON 文件：简单，适合小规模")
    print("  2. SQLite：结构化，适合中等规模")
    print("  3. Redis：快速，适合缓存")
    print("  4. PostgreSQL/MySQL：适合大规模生产")
    print("  5. 向量数据库：适合语义检索\n")
    
    print(f"{Fore.GREEN}建议:{Style.RESET_ALL}")
    print("  - 开发/测试：JSON 文件")
    print("  - 小型应用：SQLite")
    print("  - 生产环境：PostgreSQL + Redis")
    print("  - 需要检索：向量数据库（如 Pinecone、Weaviate）\n")


if __name__ == "__main__":
    main()
