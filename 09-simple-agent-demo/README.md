# 简单 Agent 演示

基于 Function Call 构建的 AI Agent，支持自主决策、多步执行、记忆管理。

## Agent 是什么？

**Agent = Function Call + 自主决策 + 记忆管理**

### 与 Function Call 的区别

| 特性 | Function Call | Agent |
|------|--------------|-------|
| 调用次数 | 单次 | 多次迭代 |
| 决策者 | 人工决定 | AI 自主决定 |
| 记忆 | 无 | 记住之前的结果 |
| 适用场景 | 简单任务 | 复杂任务 |

### Agent 工作流程

```
1. 接收任务
   ↓
2. 分析任务，决定是否需要工具
   ↓
3. 如果需要 → 调用工具获取信息
   ↓
4. 获取工具结果
   ↓
5. 重复 2-4，直到信息足够
   ↓
6. 综合信息，给出最终答案
```

---

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 基础演示
python demo.py

# 实战案例：代码审查 Agent
python code_review_agent.py
```

---

## 核心特性

### 1. 自主决策
Agent 自己决定：
- 是否需要调用工具
- 调用哪个工具
- 什么时候停止

### 2. 多步执行
可以连续调用多个工具：
```
任务: 对比北京和上海的天气

步骤1: 调用 get_weather("北京")
步骤2: 调用 get_weather("上海")
步骤3: 综合信息，给出对比结果
```

### 3. 记忆管理
记住之前的工具调用结果：
```
任务: 计算 1999 * 3，然后搜索这个价格的产品

步骤1: 调用 calculate("1999 * 3") → 5997
步骤2: 记住结果 5997
步骤3: 调用 search_database("价格5997") → 使用之前的结果
```

### 4. 错误处理
工具失败后可以：
- 重试
- 换其他工具
- 调整参数

---

## 代码示例

### 基础用法

```python
from agent import SimpleAgent

# 创建 Agent
agent = SimpleAgent(max_iterations=10)

# 运行任务
result = agent.run("北京今天天气怎么样？")
print(result)

# 查看工具调用记录
for call in agent.get_tool_calls():
    print(f"工具: {call['tool']}")
    print(f"参数: {call['arguments']}")
    print(f"结果: {call['result']}")
```

### 自定义 Agent

```python
from agent import Agent

class MyAgent(Agent):
    def __init__(self):
        # 定义工具
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "my_tool",
                    "description": "我的工具",
                    "parameters": {...}
                }
            }
        ]
        super().__init__(tools, max_iterations=10)
    
    def execute_tool(self, tool_name, arguments):
        """实现工具逻辑"""
        if tool_name == "my_tool":
            # 你的工具实现
            return {"result": "..."}
```

---

## 实战案例

### 代码审查 Agent

自动审查代码，检测安全和性能问题。

**工作流程：**
1. 读取代码文件
2. 检查安全问题（SQL注入、XSS、硬编码密码）
3. 检查性能问题（嵌套循环、重复计算）
4. 为每个问题生成修复建议
5. 生成完整的审查报告

**运行：**
```bash
python code_review_agent.py
```

**示例输出：**
```
--- 第 1 轮 ---
🔧 调用工具: read_code_file
   参数: {"filepath": "test_code.py"}
   结果: {"content": "...", "lines": 20}

--- 第 2 轮 ---
🔧 调用工具: check_security
   参数: {"code": "..."}
   结果: {"issues_found": 2, "issues": [...]}

--- 第 3 轮 ---
🔧 调用工具: check_performance
   参数: {"code": "..."}
   结果: {"issues_found": 2, "issues": [...]}

--- 第 4 轮 ---
🔧 调用工具: suggest_fix
   参数: {"issue": "硬编码密码", "code": "..."}
   结果: {"suggestion": "使用环境变量..."}

✅ 最终答案:
【严重程度】: critical
【问题列表】:
1. [安全] 硬编码密码
   修复建议: 使用环境变量或配置文件
2. [安全] SQL注入风险
   修复建议: 使用参数化查询
...
```

---

## Agent 架构

### 核心组件

```python
class Agent:
    def __init__(self, tools, max_iterations):
        self.tools = tools              # 可用工具列表
        self.max_iterations = max_iterations  # 最大迭代次数
        self.memory = []                # 对话历史
        self.tool_results = []          # 工具调用记录
    
    def run(self, task):
        """运行 Agent 完成任务"""
        # 1. 初始化对话
        # 2. 迭代执行
        # 3. 返回最终答案
    
    def call_llm(self, messages):
        """调用 LLM"""
        # 发送请求到 LLM API
    
    def execute_tool(self, tool_name, arguments):
        """执行工具"""
        # 需要子类实现
```

### 关键设计

1. **迭代执行**
   - 最多执行 `max_iterations` 轮
   - 每轮可能调用工具或给出答案
   - 防止无限循环

2. **记忆管理**
   - `memory`: 完整的对话历史
   - `tool_results`: 工具调用记录
   - 每次调用 LLM 都带上完整历史

3. **工具抽象**
   - `execute_tool()` 方法由子类实现
   - 支持任意工具
   - 统一的错误处理

---

## 最佳实践

### 1. 设置合理的最大迭代次数

```python
# 简单任务
agent = SimpleAgent(max_iterations=5)

# 复杂任务
agent = SimpleAgent(max_iterations=15)
```

### 2. 提供清晰的工具描述

```python
{
    "name": "search_database",
    "description": "搜索数据库中的产品信息",  # 清晰的描述
    "parameters": {
        "query": {
            "description": "搜索关键词"  # 参数说明
        }
    }
}
```

### 3. 处理工具错误

```python
def execute_tool(self, tool_name, arguments):
    try:
        # 工具逻辑
        return {"result": "..."}
    except Exception as e:
        return {"error": str(e)}  # 返回错误信息
```

### 4. 限制工具输出大小

```python
def execute_tool(self, tool_name, arguments):
    if tool_name == "read_file":
        content = read_file(...)
        return {
            "content": content[:1000],  # 限制长度
            "truncated": len(content) > 1000
        }
```

---

## 常见问题

### Q: Agent 和 Function Call 有什么区别？

**Function Call:**
- 单次调用
- 人工决定调用哪个函数
- 适合简单任务

**Agent:**
- 多次迭代
- AI 自主决定调用顺序
- 适合复杂任务

### Q: Agent 会不会无限循环？

不会。通过 `max_iterations` 限制最大迭代次数。

### Q: 如何添加新工具？

1. 在 `tools` 列表中添加工具定义
2. 在 `execute_tool()` 中实现工具逻辑

### Q: Agent 的成本如何？

每轮迭代都会调用 LLM，成本 = 迭代次数 × 单次调用成本。

建议：
- 设置合理的 `max_iterations`
- 优化工具描述，减少不必要的调用

---

## 进阶话题

### 1. 规划（Planning）

让 Agent 先制定计划，再执行：

```python
system_prompt = """
你是规划型 Agent。

工作流程:
1. 分析任务
2. 制定步骤计划
3. 逐步执行计划
4. 根据结果调整计划
"""
```

### 2. 反思（Reflection）

让 Agent 检查自己的输出：

```python
# 添加反思工具
{
    "name": "reflect",
    "description": "检查之前的输出是否正确",
    "parameters": {...}
}
```

### 3. 多 Agent 协作

多个 Agent 分工合作：

```python
# Agent 1: 信息收集
collector = CollectorAgent()

# Agent 2: 分析
analyzer = AnalyzerAgent()

# Agent 3: 决策
decider = DeciderAgent()
```

---

## 核心要点

> **Agent = Function Call + 自主决策 + 记忆管理**

**Agent 的价值：**
1. ✅ 自动化复杂任务
2. ✅ 减少人工干预
3. ✅ 一致性和可重复性
4. ✅ 可扩展（容易添加新工具）

**适用场景：**
- ✅ 需要多步骤的任务
- ✅ 需要综合多个信息源
- ✅ 需要自主决策
- ❌ 简单的单步任务（用 Function Call 就够了）

**未来趋势：**
- 📈 Agent 会越来越重要
- 📈 更强的规划和推理能力
- 📈 多 Agent 协作
- 📈 更好的工具生态

---

## 参考资源

- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [LangChain Agents](https://python.langchain.com/docs/modules/agents/)
- [AutoGPT](https://github.com/Significant-Gravitas/AutoGPT)
- [BabyAGI](https://github.com/yoheinakajima/babyagi)
