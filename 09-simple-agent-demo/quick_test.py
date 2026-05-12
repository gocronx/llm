"""
快速测试单个任务
"""

from agent import SimpleAgent

# 创建 Agent
agent = SimpleAgent(max_iterations=3)

# 测试简单任务
print("测试: 北京天气")
print("="*60)
result = agent.run("北京今天天气怎么样？", verbose=True)

print("\n结果:", result[:100] if len(result) > 100 else result)
print("\n工具调用次数:", len(agent.get_tool_calls()))
