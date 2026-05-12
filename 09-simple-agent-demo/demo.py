"""
Agent 演示
展示 Agent 如何自主完成复杂任务
"""

from agent import SimpleAgent
from colorama import Fore, Style, init

init(autoreset=True)


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{title}")
    print(f"{'='*60}{Style.RESET_ALL}\n")


def main():
    print_section("简单 Agent 演示")
    
    print(f"{Fore.YELLOW}Agent 能力:{Style.RESET_ALL}")
    print("1. 自主规划任务步骤")
    print("2. 调用工具获取信息")
    print("3. 综合信息给出答案")
    print("4. 处理多步骤任务\n")
    
    # 创建 Agent
    agent = SimpleAgent(max_iterations=10)
    
    # 测试案例 1: 单步任务
    print_section("案例 1: 单步任务（查询天气）")
    task1 = "北京今天天气怎么样？"
    agent.run(task1, verbose=True)
    agent.reset()
    
    # 测试案例 2: 多步任务
    print_section("案例 2: 多步任务（计算 + 搜索）")
    task2 = "帮我计算 1999 * 3，然后搜索价格在这个范围内的产品"
    agent.run(task2, verbose=True)
    agent.reset()
    
    # 测试案例 3: 复杂任务
    print_section("案例 3: 复杂任务（多次工具调用）")
    task3 = "对比北京和上海的天气，告诉我哪个城市更适合户外活动"
    agent.run(task3, verbose=True)
    agent.reset()
    
    # 测试案例 4: 需要推理的任务
    print_section("案例 4: 推理任务（搜索 + 计算）")
    task4 = "搜索所有手机产品，计算它们的平均价格"
    agent.run(task4, verbose=True)
    agent.reset()
    
    # 总结
    print_section("Agent 工作原理")
    
    print(f"{Fore.GREEN}核心流程:{Style.RESET_ALL}\n")
    print("1. 接收任务")
    print("   ↓")
    print("2. 分析任务，决定是否需要工具")
    print("   ↓")
    print("3. 如果需要 → 调用工具获取信息")
    print("   ↓")
    print("4. 获取工具结果")
    print("   ↓")
    print("5. 重复 2-4，直到信息足够")
    print("   ↓")
    print("6. 综合信息，给出最终答案\n")
    
    print(f"{Fore.GREEN}关键特性:{Style.RESET_ALL}\n")
    print("✓ 自主决策 - Agent 自己决定调用哪个工具")
    print("✓ 多步执行 - 可以连续调用多个工具")
    print("✓ 记忆管理 - 记住之前的工具调用结果")
    print("✓ 错误处理 - 工具失败后可以重试或换方案\n")
    
    print(f"{Fore.YELLOW}与 Function Call 的区别:{Style.RESET_ALL}\n")
    print("Function Call:")
    print("  - 单次调用")
    print("  - 人工决定调用哪个函数")
    print("  - 适合简单任务\n")
    
    print("Agent:")
    print("  - 多次迭代")
    print("  - AI 自主决定调用顺序")
    print("  - 适合复杂任务\n")
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Agent = Function Call + 自主决策 + 记忆管理{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
