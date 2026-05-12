# LLM Function Call 原理示例项目

## 项目简介

这个项目演示了 LLM (大语言模型) Function Calling 的工作原理。通过实际代码展示：
- 如何定义函数工具
- 如何让 LLM 理解并调用函数
- 完整的请求-响应流程
- **真实的 LLM API 调用（支持多种模型）**

## Function Call 原理

Function Calling 允许 LLM 调用外部函数来获取信息或执行操作。工作流程：

1. **定义函数模式** - 用 JSON Schema 描述函数的名称、参数、功能
2. **发送请求** - 将用户问题和可用函数列表发送给 LLM
3. **LLM 决策** - LLM 分析问题，决定是否需要调用函数
4. **执行函数** - 根据 LLM 返回的函数名和参数，执行实际函数
5. **返回结果** - 将函数执行结果返回给 LLM
6. **生成回答** - LLM 基于函数结果生成最终答案

## 项目结构

```
01-llm-function-call-demo/
├── README.md                    # 项目说明
├── TUTORIAL.md                  # 深度教程
├── requirements.txt             # Python 依赖
├── .env.example                 # 环境变量示例
├── .env                         # 环境变量配置（需自行创建）
├── llm_client.py                # 统一的 LLM 客户端
├── function_definitions.py      # 函数定义和实现
├── simple_example.py            # 简单示例：模拟 function call
├── manual_simulation.py         # 手动模拟完整流程
├── openai_example.py            # 真实 LLM API 调用示例
└── test_connection.py           # 测试 API 连接
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API

复制 `.env.example` 为 `.env` 并填入你的配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# 选择你的模型提供商
MODEL_PROVIDER=openai

# 填入你的 API 配置
API_KEY=your-api-key-here
API_BASE_URL=https://api.openai.com/v1
MODEL_ID=gpt-4-turbo-preview
```

### 3. 测试连接

```bash
python test_connection.py
```

### 4. 运行示例

```bash
# 简单模拟示例（无需 API）
python simple_example.py

# 手动模拟完整流程
python manual_simulation.py

# 真实 LLM API 调用
python openai_example.py
```

## 支持的模型提供商

### OpenAI 官方

```bash
MODEL_PROVIDER=openai
API_KEY=sk-xxx
API_BASE_URL=https://api.openai.com/v1
MODEL_ID=gpt-4-turbo-preview
```

### 智谱 AI (ChatGLM)

```bash
MODEL_PROVIDER=zhipu
API_KEY=your-zhipu-key
API_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL_ID=glm-4
```

### 阿里通义千问

```bash
MODEL_PROVIDER=qwen
API_KEY=your-qwen-key
API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_ID=qwen-turbo
```

### DeepSeek

```bash
MODEL_PROVIDER=deepseek
API_KEY=your-deepseek-key
API_BASE_URL=https://api.deepseek.com/v1
MODEL_ID=deepseek-chat
```

### 自定义（兼容 OpenAI API 的服务）

```bash
MODEL_PROVIDER=custom
API_KEY=your-custom-key
API_BASE_URL=http://localhost:8000/v1
MODEL_ID=your-model-name
```

## 核心概念

### 函数定义格式

```python
{
    "name": "get_weather",
    "description": "获取指定城市的天气信息",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "城市名称"
            }
        },
        "required": ["city"]
    }
}
```

### 调用流程

```
用户: "北京今天天气怎么样？"
  ↓
LLM 分析: 需要调用 get_weather 函数
  ↓
返回: function_call = {name: "get_weather", arguments: {"city": "北京"}}
  ↓
执行函数: get_weather("北京") → "晴天，25°C"
  ↓
LLM 生成: "北京今天天气晴朗，温度25摄氏度"
```

## 示例功能

项目包含三个可调用的函数：

1. **get_weather** - 查询城市天气
2. **calculate** - 执行数学计算
3. **search_database** - 搜索数据库

你可以在 `function_definitions.py` 中添加自己的函数。

## 学习路径

1. **阅读** `README.md` 了解整体概念 ✓
2. **配置** `.env` 文件设置 API
3. **运行** `test_connection.py` 测试连接
4. **运行** `simple_example.py` 看模拟效果
5. **运行** `openai_example.py` 看真实调用
6. **阅读** `TUTORIAL.md` 深入学习原理
7. **修改** `function_definitions.py` 添加自己的函数

## 常见问题

### Q: 如何切换不同的模型？

A: 修改 `.env` 文件中的 `MODEL_PROVIDER`、`API_KEY`、`API_BASE_URL` 和 `MODEL_ID`。

### Q: 支持哪些模型？

A: 支持所有兼容 OpenAI API 格式的模型，包括 OpenAI、智谱、通义千问、DeepSeek 等。

### Q: 如何添加自己的函数？

A: 在 `function_definitions.py` 中：
1. 实现 Python 函数
2. 添加 JSON Schema 定义
3. 在 `execute_function` 中注册

### Q: API 调用失败怎么办？

A: 
1. 运行 `python test_connection.py` 检查配置
2. 确认 API_KEY 是否正确
3. 确认网络连接是否正常
4. 查看错误信息进行排查

## 参考资料

- [OpenAI Function Calling 文档](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic Claude Tools 文档](https://docs.anthropic.com/claude/docs/tool-use)
- [智谱 AI 文档](https://open.bigmodel.cn/dev/api)
- [通义千问文档](https://help.aliyun.com/zh/dashscope/)

## 许可证

MIT License
