"""
MCP Client 示例
连接 MCP Server 并通过 LLM 调用工具
"""

import os
import json
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


class SimpleMCPClient:
    """简化的 MCP Client（用于演示）"""
    
    def __init__(self):
        self.tools = []
        self.tool_handlers = {}
    
    def register_tool(self, tool: Dict[str, Any], handler):
        """注册工具"""
        self.tools.append(tool)
        self.tool_handlers[tool["name"]] = handler
    
    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """调用工具"""
        if name not in self.tool_handlers:
            return f"未知工具: {name}"
        
        handler = self.tool_handlers[name]
        return handler(arguments)
    
    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """获取 OpenAI 格式的工具定义"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["inputSchema"]
                }
            }
            for tool in self.tools
        ]
    
    def chat(self, messages: List[Dict[str, str]], max_rounds: int = 5) -> str:
        """与 LLM 对话（支持工具调用）"""
        
        for round_num in range(1, max_rounds + 1):
            print(f"\n{Fore.CYAN}--- 第 {round_num} 轮 ---{Style.RESET_ALL}\n")
            
            # 调用 LLM
            response = requests.post(
                f"{API_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL_ID,
                    "messages": messages,
                    "tools": self.get_tools_for_llm()
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return f"API 错误: {response.status_code}"
            
            result = response.json()
            choice = result["choices"][0]
            message = choice["message"]
            
            # 检查是否有工具调用
            if "tool_calls" in message and message["tool_calls"]:
                # 添加助手消息
                messages.append(message)
                
                # 执行工具调用
                for tool_call in message["tool_calls"]:
                    function_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])
                    
                    print(f"{Fore.YELLOW}🔧 调用工具:{Style.RESET_ALL} {function_name}")
                    print(f"{Fore.YELLOW}   参数:{Style.RESET_ALL} {json.dumps(arguments, ensure_ascii=False)}")
                    
                    # 调用工具
                    tool_result = self.call_tool(function_name, arguments)
                    
                    print(f"{Fore.YELLOW}   结果:{Style.RESET_ALL} {tool_result[:100]}...")
                    
                    # 添加工具结果
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": tool_result
                    })
                
                # 继续下一轮
                continue
            
            else:
                # 没有工具调用，返回最终答案
                print(f"\n{Fore.GREEN}✅ 最终答案:{Style.RESET_ALL}\n")
                return message["content"]
        
        return "达到最大轮数限制"


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("MCP (Model Context Protocol) 演示")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 创建 MCP Client
    client = SimpleMCPClient()
    
    # 注册文件系统工具（模拟 MCP Server）
    import os
    
    base_path = os.path.abspath("test_workspace")
    os.makedirs(base_path, exist_ok=True)
    
    def read_file(args):
        path = os.path.join(base_path, args["path"])
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"读取失败: {str(e)}"
    
    def write_file(args):
        path = os.path.join(base_path, args["path"])
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(args["content"])
            return f"成功写入文件: {args['path']}"
        except Exception as e:
            return f"写入失败: {str(e)}"
    
    def list_directory(args):
        path = os.path.join(base_path, args.get("path", "."))
        try:
            items = os.listdir(path)
            result = []
            for item in items:
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    result.append(f"📁 {item}/")
                else:
                    size = os.path.getsize(item_path)
                    result.append(f"📄 {item} ({size} bytes)")
            return "\n".join(result) if result else "目录为空"
        except Exception as e:
            return f"列出目录失败: {str(e)}"
    
    # 注册工具
    client.register_tool({
        "name": "read_file",
        "description": "读取文件内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"]
        }
    }, read_file)
    
    client.register_tool({
        "name": "write_file",
        "description": "写入文件内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"}
            },
            "required": ["path", "content"]
        }
    }, write_file)
    
    client.register_tool({
        "name": "list_directory",
        "description": "列出目录内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径", "default": "."}
            }
        }
    }, list_directory)
    
    # 测试场景
    print(f"{Fore.GREEN}场景:{Style.RESET_ALL} 让 AI 创建一个 TODO 列表文件\n")
    print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    messages = [
        {
            "role": "user",
            "content": "请帮我创建一个 todo.txt 文件，内容包括：1. 学习 MCP 协议 2. 实现 MCP Server 3. 测试 MCP Client"
        }
    ]
    
    result = client.chat(messages)
    print(result)
    
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 验证文件
    print(f"{Fore.GREEN}验证:{Style.RESET_ALL} 检查文件是否创建成功\n")
    
    messages2 = [
        {
            "role": "user",
            "content": "请列出当前目录的文件，然后读取 todo.txt 的内容"
        }
    ]
    
    result2 = client.chat(messages2)
    print(result2)
    
    print(f"\n{Fore.CYAN}{'='*60}")
    print("MCP 的价值")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}MCP vs Function Call:{Style.RESET_ALL}\n")
    print("Function Call:")
    print("  - 每个应用自己定义工具格式")
    print("  - 没有统一标准")
    print("  - 难以复用\n")
    
    print("MCP:")
    print("  - 统一的协议标准")
    print("  - Server 可以被多个 Client 复用")
    print("  - 生态系统更健康\n")
    
    print(f"{Fore.GREEN}结论:{Style.RESET_ALL}")
    print("  MCP 是 Function Call 的标准化演进")
    print("  长期价值更高\n")


if __name__ == "__main__":
    main()
