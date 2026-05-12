"""
手动模拟完整的 Function Call 流程
展示每一步的详细过程，帮助理解原理
"""

import json
from function_definitions import FUNCTION_DEFINITIONS, execute_function


class FunctionCallSimulator:
    """Function Call 流程模拟器"""
    
    def __init__(self):
        self.conversation_history = []
        self.available_functions = FUNCTION_DEFINITIONS
    
    def print_step(self, step_num: int, title: str, content: str, color: str = "blue"):
        """打印步骤信息"""
        colors = {
            "blue": "\033[94m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "red": "\033[91m",
            "end": "\033[0m"
        }
        
        print(f"\n{colors.get(color, '')}")
        print(f"{'=' * 70}")
        print(f"步骤 {step_num}: {title}")
        print(f"{'=' * 70}")
        print(f"{colors['end']}")
        print(content)
    
    def step1_user_input(self, user_message: str):
        """步骤1：用户输入"""
        self.print_step(1, "用户输入", f"用户问题: {user_message}", "blue")
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        return user_message
    
    def step2_prepare_request(self):
        """步骤2：准备发送给 LLM 的请求"""
        request_data = {
            "model": "gpt-4",
            "messages": self.conversation_history,
            "functions": self.available_functions,
            "function_call": "auto"  # auto 表示让 LLM 自动决定是否调用函数
        }
        
        content = "准备发送给 LLM 的请求数据:\n\n"
        content += f"模型: {request_data['model']}\n"
        content += f"对话历史: {len(self.conversation_history)} 条消息\n"
        content += f"可用函数: {len(self.available_functions)} 个\n\n"
        content += "可用函数列表:\n"
        for func in self.available_functions:
            content += f"  - {func['name']}: {func['description']}\n"
        
        self.print_step(2, "准备 API 请求", content, "blue")
        return request_data
    
    def step3_llm_analysis(self, user_message: str):
        """步骤3：LLM 分析并决策"""
        content = "LLM 正在分析:\n"
        content += f"  1. 理解用户意图\n"
        content += f"  2. 检查是否需要外部数据或计算\n"
        content += f"  3. 匹配合适的函数\n"
        content += f"  4. 提取函数所需的参数\n\n"
        
        # 模拟 LLM 的决策
        if "天气" in user_message:
            cities = ["北京", "上海", "深圳", "成都"]
            city = next((c for c in cities if c in user_message), "北京")
            
            llm_response = {
                "role": "assistant",
                "content": None,
                "function_call": {
                    "name": "get_weather",
                    "arguments": json.dumps({"city": city, "unit": "celsius"}, ensure_ascii=False)
                }
            }
            content += "✓ LLM 决策结果: 需要调用函数\n"
            content += f"  函数名: {llm_response['function_call']['name']}\n"
            content += f"  参数: {llm_response['function_call']['arguments']}\n"
        else:
            llm_response = {
                "role": "assistant",
                "content": "我可以帮你查询天气、进行计算或搜索数据。"
            }
            content += "✓ LLM 决策结果: 直接回答，无需调用函数\n"
        
        self.print_step(3, "LLM 分析与决策", content, "yellow")
        return llm_response
    
    def step4_execute_function(self, function_call: dict):
        """步骤4：执行函数调用"""
        function_name = function_call["name"]
        function_args = json.loads(function_call["arguments"])
        
        content = f"执行函数调用:\n"
        content += f"  函数名: {function_name}\n"
        content += f"  参数: {json.dumps(function_args, ensure_ascii=False, indent=4)}\n\n"
        
        # 执行函数
        result = execute_function(function_name, function_args)
        
        content += f"✓ 函数执行成功\n"
        content += f"  返回结果:\n"
        content += f"  {result}\n"
        
        self.print_step(4, "执行函数", content, "green")
        
        # 将函数调用和结果添加到对话历史
        self.conversation_history.append({
            "role": "assistant",
            "content": None,
            "function_call": function_call
        })
        self.conversation_history.append({
            "role": "function",
            "name": function_name,
            "content": result
        })
        
        return result
    
    def step5_final_response(self, function_result: str):
        """步骤5：LLM 生成最终回答"""
        content = "LLM 基于函数结果生成自然语言回答:\n\n"
        
        result_data = json.loads(function_result)
        
        # 生成最终回答
        if "condition" in result_data:
            final_answer = f"{result_data['city']}今天的天气是{result_data['condition']}，" \
                          f"温度{result_data['temperature']}，湿度{result_data['humidity']}。"
        else:
            final_answer = "已为您查询完成。"
        
        content += f"✓ 最终回答: {final_answer}\n"
        
        self.print_step(5, "生成最终回答", content, "green")
        
        self.conversation_history.append({
            "role": "assistant",
            "content": final_answer
        })
        
        return final_answer
    
    def run_complete_flow(self, user_message: str):
        """运行完整的 Function Call 流程"""
        print("\n" + "🎯 " * 30)
        print("完整 Function Call 流程演示")
        print("🎯 " * 30)
        
        # 步骤1：用户输入
        self.step1_user_input(user_message)
        
        # 步骤2：准备请求
        self.step2_prepare_request()
        
        # 步骤3：LLM 分析
        llm_response = self.step3_llm_analysis(user_message)
        
        # 步骤4 & 5：如果需要调用函数
        if llm_response.get("function_call"):
            function_result = self.step4_execute_function(llm_response["function_call"])
            final_answer = self.step5_final_response(function_result)
        else:
            print("\n✓ 流程结束：LLM 直接回答，无需函数调用")
        
        print("\n" + "=" * 70)
        print("流程完成！")
        print("=" * 70 + "\n")


def explain_architecture():
    """解释 Function Call 的架构"""
    print("\n" + "📚 " * 30)
    print("Function Call 架构说明")
    print("📚 " * 30 + "\n")
    
    architecture = """
┌─────────────────────────────────────────────────────────────────┐
│                     Function Call 完整流程                        │
└─────────────────────────────────────────────────────────────────┘

1️⃣  用户输入
    │
    ├─→ "北京今天天气怎么样？"
    │

2️⃣  构建请求 (包含函数定义)
    │
    ├─→ {
    │     "messages": [...],
    │     "functions": [
    │       {
    │         "name": "get_weather",
    │         "description": "获取天气信息",
    │         "parameters": {...}
    │       }
    │     ]
    │   }
    │

3️⃣  LLM 分析与决策
    │
    ├─→ 分析: "用户想知道北京天气"
    ├─→ 决策: "需要调用 get_weather 函数"
    ├─→ 提取参数: {"city": "北京"}
    │
    └─→ 返回: {
          "function_call": {
            "name": "get_weather",
            "arguments": "{\\"city\\": \\"北京\\"}"
          }
        }

4️⃣  执行函数
    │
    ├─→ 解析函数名和参数
    ├─→ 调用实际的 Python 函数
    ├─→ get_weather(city="北京")
    │
    └─→ 返回: {"city": "北京", "condition": "晴天", "temperature": "25°C"}

5️⃣  将结果返回给 LLM
    │
    ├─→ 添加函数结果到对话历史
    ├─→ 再次调用 LLM API
    │

6️⃣  LLM 生成最终回答
    │
    └─→ "北京今天的天气是晴天，温度25°C，湿度45%。"


🔑 关键点:

• 函数定义使用 JSON Schema 格式
• LLM 不会真正执行函数，只是返回调用指令
• 我们的代码负责实际执行函数
• 可能需要多轮对话（LLM → 函数 → LLM）
• 函数结果必须是字符串格式
"""
    
    print(architecture)


def main():
    """主函数"""
    # 先解释架构
    explain_architecture()
    
    input("\n按 Enter 键开始演示...")
    
    # 运行完整流程演示
    simulator = FunctionCallSimulator()
    simulator.run_complete_flow("上海今天天气怎么样？")
    
    print("\n💡 学习要点:")
    print("  1. Function Call 是一个多步骤的协作过程")
    print("  2. LLM 负责理解意图和生成参数")
    print("  3. 我们的代码负责实际执行函数")
    print("  4. 函数定义的质量直接影响 LLM 的决策准确性")
    print("  5. 整个过程是可控和可调试的\n")


if __name__ == "__main__":
    main()
