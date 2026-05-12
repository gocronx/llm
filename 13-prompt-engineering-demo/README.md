# Prompt Engineering 实战

## ⚠️ 重要说明

**随着模型能力越来越强，Prompt Engineering 的价值正在下降。**

- **2023 年**：需要精心设计 Prompt 才能得到好结果
- **2024 年**：强大的模型（GPT-4、Claude、Qwen）简单 Prompt 就很好
- **未来**：可能只需要说"做什么"，不需要说"怎么做"

**当前价值：**
1. ✅ **格式控制** - 输出 JSON 而不是 Markdown
2. ✅ **字段名统一** - name vs 姓名
3. ✅ **推理可验证** - 展示推理步骤
4. ❌ **不是提高质量** - 模型已经很强

**本项目的定位：**
- 了解 Prompt Engineering 的基本概念
- 知道如何控制输出格式
- 但不要过度投入时间

---

## 核心技术

1. **System Prompt** - 定义 AI 角色和行为
2. **Few-shot Learning** - 统一输出格式和字段名
3. **Chain of Thought** - 让推理过程可验证
4. **Structured Output** - 控制输出格式便于程序处理

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 交互式测试工具（推荐）
python playground.py

# 技术对比演示
python compare_techniques.py

# Prompt 模板库
python templates.py

# 单个技术演示
python techniques/system_prompt.py
python techniques/few_shot.py
python techniques/chain_of_thought.py
python techniques/structured_output.py

# 实战案例
python examples/code_review.py      # 代码审查
python examples/input_validation.py # 输入验证
```

## 技术详解

### 1. System Prompt

定义 AI 的角色和行为。

**差的示例：**
```python
system = "你是一个助手"
```

**好的示例：**
```python
system = """你是资深 Python 安全工程师。

职责:
1. 识别安全漏洞
2. 评估代码质量
3. 提供改进建议

风格: 专业、客观、建设性
"""
```

---

### 2. Few-shot Learning

通过示例引导输出格式。

**Zero-shot（无示例）：**
```python
prompt = "提取姓名、年龄、职位，输出 JSON"
```

**Few-shot（有示例）：**
```python
prompt = """提取信息并输出 JSON。

示例:
输入: "张三，28岁，Python工程师"
输出: {"name": "张三", "age": 28, "position": "Python工程师"}

现在处理:
输入: {text}
输出:"""
```

---

### 3. Chain of Thought

让模型展示推理过程，提高准确率。

**直接问答：**
```python
prompt = "156 除以 12 等于多少？"
```

**Chain of Thought：**
```python
prompt = """请一步步思考：

问题: 156 除以 12 等于多少？

思考过程:
1. 估算范围
2. 精确计算
3. 验证结果

答案:"""
```

---

### 4. Structured Output

控制输出格式，便于程序处理。

**示例：**
```python
prompt = """分析代码并输出 JSON:

{
  "score": 1-10,
  "issues": [
    {
      "type": "security/bug/performance",
      "description": "问题描述",
      "suggestion": "改进建议"
    }
  ]
}

代码:
{code}
"""
```

## 最佳实践

### ✅ 该做的

1. **明确具体** - 清楚说明你要什么
2. **提供示例** - Few-shot 比 Zero-shot 好
3. **分步骤** - 复杂任务拆分
4. **设定角色** - 让 AI 扮演专家
5. **限制输出** - 指定格式、长度
6. **迭代优化** - 测试并改进

### ❌ 不该做的

1. **模糊不清** - "帮我处理一下"
2. **过于复杂** - 一个 Prompt 做太多事
3. **没有示例** - 期望 AI 猜测格式
4. **忽略上下文** - 不提供必要信息
5. **不测试** - 写完就用

## 效果对比

**重要说明：** 对于强大的模型，Prompt Engineering 的价值不是提高质量，而是：

1. **格式控制** - JSON vs Markdown vs 自由文本
2. **字段名统一** - name vs 姓名（英文 vs 中文）
3. **推理可验证** - 展示推理步骤便于调试

**示例：数据提取**

| Prompt 类型 | 字段名 | 格式一致性 |
|------------|--------|-----------|
| Zero-shot | 随机（中文或英文） | 60% |
| Few-shot | 固定（按示例） | 95% |

**结论：Few-shot 的价值在于统一格式，而不是提高准确率。**

## 实战案例

### 1. 代码审查工具

```python
# System Prompt: 定义专家角色
system = """你是资深 Python 安全工程师。

职责:
1. 识别安全漏洞（SQL注入、XSS、硬编码密码）
2. 评估代码质量
3. 提供改进建议

风格: 专业、客观、建设性
"""

# User Prompt: 结构化输出
user = f"""审查代码并输出 JSON:

{{
  "score": 1-10,
  "severity": "critical/high/medium/low",
  "issues": [
    {{
      "type": "security/bug/performance",
      "description": "问题描述",
      "suggestion": "改进建议"
    }}
  ]
}}

代码:
```python
{code}
```
"""
```

运行：
```bash
python examples/code_review.py
```

---

### 2. 输入验证工具

使用 LLM 验证和清洗用户输入，检测安全威胁。

**支持的验证类型：**

1. **邮箱验证** - 格式检查和标准化
2. **手机号验证** - 支持多种格式，自动标准化
3. **SQL 注入检测** - 识别 SQL 注入风险
4. **XSS 攻击检测** - 识别跨站脚本攻击

**示例：**

```python
# 邮箱验证
输入: "user@example.com"
输出: {"valid": true, "normalized": "user@example.com"}

输入: "invalid.email"
输出: {"valid": false, "issues": ["缺少 @ 符号"], "suggestion": "邮箱格式应为: username@domain.com"}

# SQL 注入检测
输入: "张三"
输出: {"safe": true, "risk_level": "safe"}

输入: "admin' OR '1'='1"
输出: {"safe": false, "risk_level": "critical", "threats": ["包含 SQL 注入特征"], "suggestion": "拒绝此输入"}

# XSS 攻击检测
输入: "Hello World"
输出: {"safe": true, "risk_level": "safe"}

输入: "<script>alert('XSS')</script>"
输出: {"safe": false, "risk_level": "critical", "threats": ["包含 script 标签"], "suggestion": "拒绝此输入"}
```

运行：
```bash
python examples/input_validation.py
```

**技术要点：**
- System Prompt 定义验证专家角色
- Few-shot 提供正面和负面示例
- Structured Output 便于程序处理
- 明确的验证规则和检查项

**注意：**
- LLM 验证应作为辅助手段
- 关键安全检查仍需使用专门的安全库
- 建议组合使用：LLM + 正则表达式 + 安全库

## 核心要点

> **Prompt Engineering 的价值正在下降，但格式控制仍然有用。**

**实际建议：**
1. **不要过度投入** - 模型会越来越强
2. **重点放在格式** - JSON、字段名、结构
3. **简单就好** - 不要写太复杂的 Prompt
4. **关注新技术** - Function Call、MCP、Agent 更有价值

**什么时候需要 Prompt Engineering：**
- ✅ 需要固定的 JSON 格式
- ✅ 需要统一的字段名
- ✅ 需要展示推理步骤
- ❌ 不要期望提高质量

**更有价值的技能：**
1. **Function Call** - 让 AI 调用工具
2. **MCP (Model Context Protocol)** - 标准化的工具协议
3. **Agent** - 自主决策和执行
4. **RAG** - 大规模知识库检索
