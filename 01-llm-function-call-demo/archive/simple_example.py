"""
简单示例：模拟 LLM Function Call 的工作流程
不需要真实的 API 调用，通过模拟展示核心原理
"""

import json
from function_definitions import FUNCTION_DEFINITIONS, execute_function


def simulate_llm_decision(user_message: str, available_functions: list) -> dict:
    """
    模拟 LLM 的决策过程
    在真实场景中，这部分由 LLM API 完成
    
    Args:
        user_message: 用户输入的消息
        available_functions: 可用的函数列表
    
    Returns:
        LLM 的响应，可能包含 function_call
    """
    # 简单的规则匹配来模拟 LLM 的决策
    user_message_lower = user_message.lower()
    
    # 场景1：天气查询
    if "天气" in user_message:
        cities = ["北京", "上海", "深圳", "成都"]
        city = next((c for c in cities if c in user_message), "北京")
        
        return {
            "role": "assistant",
            "content": None,
            "function_call": {
                "name": "get_weather",
                "arguments": json.dumps({"city": city, "unit": "celsius"})
            }
        }
    
    # 场景2：数学计算
    elif any(word in user_message for word in ["计算", "加", "减", "乘", "除", "等于"]):
        # 简单解析（实际 LLM 会更智能）
        if "+" in user_message or "加" in user_message:
            return {
                "role": "assistant",
                "content": None,
                "function_call": {
                    "name": "calculate",
                    "arguments": json.dumps({"operation": "add", "a": 15, "b": 27})
                }
            }
        elif "*" in user_message or "乘" in user_message:
            return {
                "role": "assistant",
                "content": None,
                "function_call": {
                    "name": "calculate",
                    "arguments": json.dumps({"operation": "multiply", "a": 12, "b": 8})
                }
            }
    
    # 场景3：搜索
    elif "搜索" in user_message or "查找" in user_message:
        return {
            "role": "assistant",
            "content": None,
            "function_call": {
                "name": "search_database",
                "arguments": json.dumps({"query": "键盘", "category": "products"})
            }
        }
    
    # 默认：不需要调用函数
    return {
        "role": "assistant",
        "content": "我是一个 AI 助手，可以帮你查询天气、进行计算或搜索数据库。请告诉我你需要什么帮助！"
    }


def simulate_final_response(user_message: str, function_result: str) -> str:
    """
    模拟 LLM 基于函数结果生成最终回答
    
    Args:
        user_message: 用户原始问题
        function_result: 函数执行结果
    
    Returns:
        最终的自然语言回答
    """
    result_data = json.loads(function_result)
    
    # 根据不同的结果类型生成回答
    if "condition" in result_data:  # 天气查询
        return f"{result_data['city']}今天的天气是{result_data['condition']}，" \
               f"温度{result_data['temperature']}，湿度{result_data['humidity']}。"
    
    elif "operation" in result_data:  # 计算
        op_names = {
            "add": "加法",
            "subtract": "减法",
            "multiply": "乘法",
            "divide": "除法"
        }
        return f"计算结果：{result_data['operand_a']} {op_names.get(result_data['operation'], '')} " \
               f"{result_data['operand_b']} = {result_data['result']}"
    
    elif "results" in result_data:  # 搜索
        if result_data['count'] > 0:
            items = ", ".join([item.get('name', str(item)) for item in result_data['results']])
            return f"找到 {result_data['count']} 条结果：{items}"
        else:
            return "没有找到相关结果。"
    
    return "处理完成。"


def run_function_call_demo(user_message: str):
    """
    运行完整的 function call 演示流程
    
    Args:
        user_message: 用户输入的消息
    """
    print("=" * 60)
    print(f"用户输入: {user_message}")
    print("=" * 60)
    
    # 步骤1：LLM 分析用户输入，决定是否调用函数
    print("\n[步骤1] LLM 分析用户输入...")
    llm_response = simulate_llm_decision(user_message, FUNCTION_DEFINITIONS)
    
    # 检查是否需要调用函数
    if llm_response.get("function_call"):
        function_call = llm_response["function_call"]
        print(f"✓ LLM 决定调用函数: {function_call['name']}")
        print(f"  参数: {function_call['arguments']}")
        
        # 步骤2：执行函数
        print("\n[步骤2] 执行函数...")
        function_name = function_call["name"]
        function_args = json.loads(function_call["arguments"])
        
        function_result = execute_function(function_name, function_args)
        print(f"✓ 函数执行结果:")
        print(f"  {function_result}")
        
        # 步骤3：LLM 基于函数结果生成最终回答
        print("\n[步骤3] LLM 生成最终回答...")
        final_answer = simulate_final_response(user_message, function_result)
        print(f"✓ 最终回答: {final_answer}")
        
    else:
        # 不需要调用函数，直接回答
        print("✓ LLM 直接回答（无需调用函数）")
        print(f"  {llm_response['content']}")
    
    print("\n" + "=" * 60 + "\n")


def main():
    """主函数：运行多个示例"""
    print("\n" + "🚀 " * 20)
    print("LLM Function Call 原理演示")
    print("🚀 " * 20 + "\n")
    
    # 示例1：天气查询
    run_function_call_demo("北京今天天气怎么样？")
    
    # 示例2：数学计算
    run_function_call_demo("帮我计算 12 * 8 等于多少")
    
    # 示例3：数据库搜索
    run_function_call_demo("搜索一下键盘相关的产品")
    
    # 示例4：普通对话（不需要函数）
    run_function_call_demo("你好，你能做什么？")
    
    print("\n💡 核心要点:")
    print("1. LLM 根据用户输入和函数定义，智能决定是否需要调用函数")
    print("2. 如果需要，LLM 会返回函数名和参数（JSON 格式）")
    print("3. 我们的代码执行实际的函数调用")
    print("4. 将函数结果返回给 LLM，LLM 生成自然语言回答")
    print("5. 整个过程可能需要多轮交互\n")


if __name__ == "__main__":
    main()
