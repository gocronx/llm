"""
简单 Agent 实现
基于 Function Call 构建，支持任务规划、工具调用、记忆管理
"""

import os
import json
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


class Agent:
    """简单的 AI Agent"""
    
    def __init__(self, tools: List[Dict], max_iterations: int = 10):
        """
        初始化 Agent
        
        Args:
            tools: 可用的工具列表（Function Call 格式）
            max_iterations: 最大迭代次数（防止无限循环）
        """
        self.tools = tools
        self.max_iterations = max_iterations
        self.memory = []  # 对话历史
        self.tool_results = []  # 工具调用结果
        
    def call_llm(self, messages: List[Dict]) -> Dict:
        """调用 LLM"""
        try:
            response = requests.post(
                f"{API_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL_ID,
                    "messages": messages,
                    "tools": self.tools,
                    "tool_choice": "auto",
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"API 错误: {response.status_code}"}
        except Exception as e:
            return {"error": f"调用失败: {e}"}
    
    def execute_tool(self, tool_name: str, arguments: Dict) -> Any:
        """
        执行工具
        这里需要实际的工具实现，现在返回模拟结果
        """
        # 这个方法应该被子类重写，或者通过依赖注入提供工具实现
        raise NotImplementedError("需要提供工具实现")
    
    def run(self, task: str, verbose: bool = True) -> str:
        """
        运行 Agent 完成任务
        
        Args:
            task: 用户任务
            verbose: 是否打印详细信息
            
        Returns:
            最终答案
        """
        # 初始化对话
        system_content = """你是一个智能助手 Agent。
                            你的能力:
                            1. 分析任务，制定计划
                            2. 调用工具完成子任务
                            3. 综合信息，给出最终答案

                            工作流程:
                            1. 理解用户任务
                            2. 如果需要信息，调用工具获取
                            3. 如果需要多个步骤，逐步执行
                            4. 综合所有信息，给出完整答案

                            注意:
                            - 一次只调用一个工具
                            - 等待工具结果后再决定下一步
                            - 如果信息足够，直接给出答案
                         """
        
        self.memory = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": task}
        ]
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"任务: {task}")
            print(f"{'='*60}\n")
        
        # 迭代执行
        for iteration in range(self.max_iterations):
            if verbose:
                print(f"--- 第 {iteration + 1} 轮 ---\n")
            
            # 调用 LLM
            response = self.call_llm(self.memory)
            
            if "error" in response:
                return f"错误: {response['error']}"
            
            message = response["choices"][0]["message"]
            
            # 检查是否有 finish_reason
            finish_reason = response["choices"][0].get("finish_reason")
            
            # 检查是否需要调用工具
            if message.get("tool_calls"):
                tool_call = message["tool_calls"][0]
                function_name = tool_call["function"]["name"]
                arguments = json.loads(tool_call["function"]["arguments"])
                
                if verbose:
                    print(f"🔧 调用工具: {function_name}")
                    print(f"   参数: {json.dumps(arguments, ensure_ascii=False)}")
                
                # 执行工具
                try:
                    result = self.execute_tool(function_name, arguments)
                    result_str = json.dumps(result, ensure_ascii=False)
                    
                    if verbose:
                        print(f"   结果: {result_str}\n")
                    
                    # 记录工具调用
                    self.tool_results.append({
                        "tool": function_name,
                        "arguments": arguments,
                        "result": result
                    })
                    
                    # 添加到对话历史
                    self.memory.append(message)
                    self.memory.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result_str
                    })
                    
                except Exception as e:
                    error_msg = f"工具执行失败: {e}"
                    if verbose:
                        print(f"   ❌ {error_msg}\n")
                    
                    self.memory.append(message)
                    self.memory.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps({"error": error_msg}, ensure_ascii=False)
                    })
            
            elif message.get("content"):
                # 有内容，说明任务完成
                final_answer = message["content"]
                
                if verbose:
                    print(f"✅ 最终答案:\n{final_answer}\n")
                    print(f"{'='*60}")
                    print(f"总共执行了 {iteration + 1} 轮")
                    print(f"调用了 {len(self.tool_results)} 次工具")
                    print(f"{'='*60}\n")
                
                return final_answer
            
            else:
                # 既没有工具调用，也没有内容 - 异常情况
                if verbose:
                    print(f"⚠️  LLM 返回空响应，停止执行\n")
                
                return "Agent 执行异常：LLM 返回空响应"
        
        # 达到最大迭代次数
        return f"达到最大迭代次数 ({self.max_iterations})，任务未完成"
    
    def get_history(self) -> List[Dict]:
        """获取对话历史"""
        return self.memory
    
    def get_tool_calls(self) -> List[Dict]:
        """获取工具调用记录"""
        return self.tool_results
    
    def reset(self):
        """重置 Agent 状态"""
        self.memory = []
        self.tool_results = []


class SimpleAgent(Agent):
    """
    简单 Agent 实现
    提供了基本的工具实现
    """
    
    def __init__(self, max_iterations: int = 10):
        # 定义可用工具
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "获取指定城市的天气信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "城市名称，例如：北京、上海"
                            }
                        },
                        "required": ["city"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "执行数学计算",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "数学表达式，例如：2 + 3 * 4"
                            }
                        },
                        "required": ["expression"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_database",
                    "description": "搜索数据库中的产品信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索关键词"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "读取文件内容",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "文件路径"
                            }
                        },
                        "required": ["filepath"]
                    }
                }
            }
        ]
        
        super().__init__(tools, max_iterations)
        
        # 模拟数据库
        self.database = [
            {"id": 1, "name": "iPhone 15", "price": 5999, "category": "手机"},
            {"id": 2, "name": "MacBook Pro", "price": 12999, "category": "电脑"},
            {"id": 3, "name": "AirPods Pro", "price": 1999, "category": "耳机"},
            {"id": 4, "name": "iPad Air", "price": 4799, "category": "平板"},
            {"id": 5, "name": "Apple Watch", "price": 2999, "category": "手表"},
        ]
    
    def execute_tool(self, tool_name: str, arguments: Dict) -> Any:
        """执行工具"""
        
        if tool_name == "get_weather":
            city = arguments["city"]
            # 模拟天气数据
            weather_data = {
                "北京": {"temperature": 15, "condition": "晴天", "humidity": 45},
                "上海": {"temperature": 20, "condition": "多云", "humidity": 60},
                "深圳": {"temperature": 25, "condition": "小雨", "humidity": 75},
            }
            return weather_data.get(city, {"error": f"未找到 {city} 的天气信息"})
        
        elif tool_name == "calculate":
            expression = arguments["expression"]
            try:
                # 安全的计算（仅支持基本运算）
                result = eval(expression, {"__builtins__": {}}, {})
                return {"result": result, "expression": expression}
            except Exception as e:
                return {"error": f"计算失败: {e}"}
        
        elif tool_name == "search_database":
            query = arguments["query"].lower()
            results = [
                item for item in self.database
                if query in item["name"].lower() or query in item["category"].lower()
            ]
            return {
                "query": arguments["query"],
                "count": len(results),
                "results": results
            }
        
        elif tool_name == "read_file":
            filepath = arguments["filepath"]
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                return {
                    "filepath": filepath,
                    "content": content[:500],  # 限制长度
                    "size": len(content)
                }
            except Exception as e:
                return {"error": f"读取文件失败: {e}"}
        
        else:
            return {"error": f"未知工具: {tool_name}"}
