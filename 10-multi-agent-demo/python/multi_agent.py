"""
Multi-Agent 协作框架
支持多个 Agent 协作完成复杂任务
"""

import os
import json
import requests
from typing import List, Dict, Any, Callable
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


class Agent:
    """单个 Agent"""
    
    def __init__(self, name: str, role: str, tools: List[Dict[str, Any]] = None):
        self.name = name
        self.role = role
        self.tools = tools or []
        self.tool_handlers = {}
    
    def register_tool(self, tool: Dict[str, Any], handler: Callable):
        """注册工具"""
        self.tools.append(tool)
        self.tool_handlers[tool["function"]["name"]] = handler
    
    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """调用工具"""
        if name not in self.tool_handlers:
            return f"未知工具: {name}"
        return self.tool_handlers[name](arguments)
    
    def execute(self, task: str, context: str = "") -> Dict[str, Any]:
        """执行任务"""
        print(f"\n{Fore.CYAN}[{self.name}] 开始执行任务{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}角色:{Style.RESET_ALL} {self.role}")
        print(f"{Fore.YELLOW}任务:{Style.RESET_ALL} {task}\n")
        
        # 构建消息 - 使用更简洁的格式
        user_content = f"{self.role}\n任务：{task}"
        if context:
            user_content += f"\n{context}"
        
        messages = [
            {
                "role": "user",
                "content": user_content
            }
        ]
        
        max_rounds = 5
        for round_num in range(1, max_rounds + 1):
            print(f"{Fore.CYAN}  轮次 {round_num}{Style.RESET_ALL}")
            
            # 调用 LLM
            request_data = {
                "model": MODEL_ID,
                "messages": messages,
                "temperature": 0.3,  # 降低温度，更确定性
                "max_tokens": 200  # 进一步限制输出长度
            }
            
            # 只有当有工具时才添加 tools 参数
            if self.tools:
                request_data["tools"] = self.tools
            
            print(f"  {Fore.YELLOW}📤 发送请求...{Style.RESET_ALL}")
            
            # Debug: 显示消息内容
            if round_num == 1:
                print(f"  {Fore.YELLOW}消息内容: {messages[0]['content'][:200]}...{Style.RESET_ALL}")
            
            try:
                response = requests.post(
                    f"{API_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=request_data,
                    timeout=60
                )
            except requests.exceptions.Timeout:
                print(f"  {Fore.RED}✗ 请求超时{Style.RESET_ALL}")
                return {
                    "success": False,
                    "error": "API 请求超时"
                }
            except Exception as e:
                print(f"  {Fore.RED}✗ 请求失败: {e}{Style.RESET_ALL}")
                return {
                    "success": False,
                    "error": f"API 请求失败: {e}"
                }
            
            print(f"  {Fore.GREEN}📥 收到响应{Style.RESET_ALL}")
            
            if response.status_code != 200:
                error_msg = f"API 错误: {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text[:200]}"
                print(f"  {Fore.RED}✗ {error_msg}{Style.RESET_ALL}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
            result = response.json()
            message = result["choices"][0]["message"]
            
            # 检查是否有工具调用
            if "tool_calls" in message and message["tool_calls"]:
                messages.append(message)
                
                for tool_call in message["tool_calls"]:
                    function_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])
                    
                    print(f"  {Fore.YELLOW}🔧 调用工具:{Style.RESET_ALL} {function_name}")
                    
                    # 调用工具
                    tool_result = self.call_tool(function_name, arguments)
                    
                    # 添加工具结果
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": tool_result
                    })
                
                continue
            
            # 没有工具调用，返回结果
            print(f"{Fore.GREEN}  ✓ 完成{Style.RESET_ALL}\n")
            return {
                "success": True,
                "result": message["content"],
                "agent": self.name
            }
        
        return {
            "success": False,
            "error": "达到最大轮数限制"
        }


class MultiAgentOrchestrator:
    """Multi-Agent 协调器"""
    
    def __init__(self):
        self.agents = {}
        self.conversation_history = []
    
    def register_agent(self, agent: Agent):
        """注册 Agent"""
        self.agents[agent.name] = agent
        print(f"{Fore.GREEN}✓ 注册 Agent:{Style.RESET_ALL} {agent.name} ({agent.role})")
    
    def execute_workflow(self, workflow: List[Dict[str, Any]]) -> Dict[str, Any]:
        """执行工作流"""
        print(f"\n{Fore.CYAN}{'='*60}")
        print("开始执行 Multi-Agent 工作流")
        print(f"{'='*60}{Style.RESET_ALL}\n")
        
        results = {}
        
        for step in workflow:
            agent_name = step["agent"]
            task = step["task"]
            
            # 构建上下文（包含之前的结果）
            context = ""
            if "depends_on" in step:
                context = "\n\n之前的结果：\n"
                for dep in step["depends_on"]:
                    if dep in results and results[dep]["success"]:
                        result_text = results[dep]['result']
                        # 限制上下文长度，避免太长
                        if len(result_text) > 300:
                            result_text = result_text[:300] + "...(已截断)"
                        context += f"\n{dep}: {result_text}\n"
            
            # 执行任务
            if agent_name not in self.agents:
                results[step.get("id", agent_name)] = {
                    "success": False,
                    "error": f"Agent {agent_name} 不存在"
                }
                continue
            
            agent = self.agents[agent_name]
            result = agent.execute(task, context)
            
            # 保存结果
            step_id = step.get("id", agent_name)
            results[step_id] = result
            
            # 如果失败，停止工作流
            if not result["success"]:
                print(f"{Fore.RED}✗ 工作流失败: {result.get('error')}{Style.RESET_ALL}")
                break
        
        print(f"\n{Fore.CYAN}{'='*60}")
        print("工作流执行完成")
        print(f"{'='*60}{Style.RESET_ALL}\n")
        
        return results
    
    def execute_parallel(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """并行执行多个任务"""
        print(f"\n{Fore.CYAN}{'='*60}")
        print("并行执行多个 Agent 任务")
        print(f"{'='*60}{Style.RESET_ALL}\n")
        
        results = {}
        
        # 简化版：顺序执行（真正的并行需要多线程）
        for task in tasks:
            agent_name = task["agent"]
            task_desc = task["task"]
            
            if agent_name not in self.agents:
                results[task.get("id", agent_name)] = {
                    "success": False,
                    "error": f"Agent {agent_name} 不存在"
                }
                continue
            
            agent = self.agents[agent_name]
            result = agent.execute(task_desc)
            
            step_id = task.get("id", agent_name)
            results[step_id] = result
        
        print(f"\n{Fore.CYAN}{'='*60}")
        print("并行任务执行完成")
        print(f"{'='*60}{Style.RESET_ALL}\n")
        
        return results


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("Multi-Agent 协作演示（简化版）")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}注意：{Style.RESET_ALL} 为了适配本地模型性能，此演示使用独立任务")
    print(f"{Fore.YELLOW}      {Style.RESET_ALL} 实际应用中，Agent 之间会传递完整上下文\n")
    
    # 创建协调器
    orchestrator = MultiAgentOrchestrator()
    
    # 创建多个 Agent
    
    # 1. 代码生成 Agent
    coder = Agent(
        name="Coder",
        role="Python 代码生成专家"
    )
    orchestrator.register_agent(coder)
    
    # 2. 测试 Agent
    tester = Agent(
        name="Tester",
        role="测试用例生成专家"
    )
    orchestrator.register_agent(tester)
    
    # 3. 审查 Agent
    reviewer = Agent(
        name="Reviewer",
        role="代码审查专家"
    )
    orchestrator.register_agent(reviewer)
    
    print()
    
    # 定义工作流（简化版，适合本地模型）
    workflow = [
        {
            "id": "generate_code",
            "agent": "Coder",
            "task": "写一个 Python 函数 fibonacci(n)。只要代码。"
        },
        {
            "id": "generate_tests",
            "agent": "Tester",
            "task": "写 3 个测试 fibonacci(0), fibonacci(1), fibonacci(5)。只要代码。"
        },
        {
            "id": "review_code",
            "agent": "Reviewer",
            "task": "说一个优点。"
        }
    ]
    
    # 执行工作流
    results = orchestrator.execute_workflow(workflow)
    
    # 显示最终结果
    print(f"{Fore.GREEN}{'='*60}")
    print("最终结果")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    for step_id, result in results.items():
        if result["success"]:
            print(f"{Fore.CYAN}[{step_id}]{Style.RESET_ALL}")
            result_text = result.get("result", "")
            if result_text:
                print(result_text[:200] + "..." if len(result_text) > 200 else result_text)
            print()
    
    # Multi-Agent 的价值
    print(f"{Fore.CYAN}{'='*60}")
    print("Multi-Agent 的价值")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}vs 单个 Agent:{Style.RESET_ALL}")
    print("  单个 Agent:")
    print("    - 需要处理所有任务")
    print("    - 容易出错")
    print("    - 难以优化\n")
    
    print("  Multi-Agent:")
    print("    ✓ 专业分工")
    print("    ✓ 每个 Agent 专注自己的领域")
    print("    ✓ 结果更可靠")
    print("    ✓ 易于扩展\n")
    
    print(f"{Fore.GREEN}结论:{Style.RESET_ALL}")
    print("  Multi-Agent 适合复杂任务")
    print("  通过协作提高质量\n")


if __name__ == "__main__":
    main()
