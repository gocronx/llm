# 使用指南

## 目录
1. [快速开始](#快速开始)
2. [配置不同的模型](#配置不同的模型)
3. [添加自定义函数](#添加自定义函数)
4. [常见问题排查](#常见问题排查)

---

## 快速开始

### 步骤 1: 安装依赖

```bash
cd 01-llm-function-call-demo
pip install -r requirements.txt
```

### 步骤 2: 配置 API

1. 复制环境变量示例文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入你的配置：
```bash
# 使用 vim、nano 或任何文本编辑器
vim .env
```

3. 最简配置（以 OpenAI 为例）：
```bash
MODEL_PROVIDER=openai
API_KEY=sk-your-actual-api-key-here
API_BASE_URL=https://api.openai.com/v1
MODEL_ID=gpt-4-turbo-preview
```

### 步骤 3: 测试连接

```bash
python test_connection.py
```

如果看到 "✓ 连接成功！"，说明配置正确。

### 步骤 4: 运行示例

```bash
# 运行真实 API 调用示例
python openai_example.py
```

---

## 配置不同的模型

### OpenAI 官方

**获取 API Key:** https://platform.openai.com/api-keys

```bash
MODEL_PROVIDER=openai
API_KEY=sk-proj-xxxxxxxxxxxxx
API_BASE_URL=https://api.openai.com/v1
MODEL_ID=gpt-4-turbo-preview
```

**可用模型:**
- `gpt-4-turbo-preview` - GPT-4 Turbo（推荐）
- `gpt-4` - GPT-4
- `gpt-3.5-turbo` - GPT-3.5（更便宜）

---

### 智谱 AI (ChatGLM)

**获取 API Key:** https://open.bigmodel.cn/

```bash
MODEL_PROVIDER=zhipu
API_KEY=your-zhipu-api-key.xxxxxxxxxxxxx
API_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL_ID=glm-4
```

**可用模型:**
- `glm-4` - GLM-4（推荐）
- `glm-3-turbo` - GLM-3 Turbo

**注意事项:**
- 智谱 AI 使用 `tools` 格式而非 `functions`
- 客户端会自动处理格式转换

---

### 阿里通义千问

**获取 API Key:** https://dashscope.aliyun.com/

```bash
MODEL_PROVIDER=qwen
API_KEY=sk-xxxxxxxxxxxxx
API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_ID=qwen-turbo
```

**可用模型:**
- `qwen-turbo` - 通义千问 Turbo（推荐）
- `qwen-plus` - 通义千问 Plus
- `qwen-max` - 通义千问 Max

---

### DeepSeek

**获取 API Key:** https://platform.deepseek.com/

```bash
MODEL_PROVIDER=deepseek
API_KEY=sk-xxxxxxxxxxxxx
API_BASE_URL=https://api.deepseek.com/v1
MODEL_ID=deepseek-chat
```

**可用模型:**
- `deepseek-chat` - DeepSeek Chat（推荐）
- `deepseek-coder` - DeepSeek Coder（代码专用）

---

### Azure OpenAI

**获取配置:** Azure Portal → Azure OpenAI Service

```bash
MODEL_PROVIDER=azure
API_KEY=your-azure-api-key
API_BASE_URL=https://your-resource-name.openai.azure.com
MODEL_ID=your-deployment-name
```

**注意事项:**
- `API_BASE_URL` 是你的 Azure 资源 URL
- `MODEL_ID` 是你的部署名称（不是模型名称）

---

### 本地模型 / 自定义 API

如果你使用 Ollama、LM Studio 或其他兼容 OpenAI API 的本地服务：

```bash
MODEL_PROVIDER=custom
API_KEY=not-needed
API_BASE_URL=http://localhost:11434/v1
MODEL_ID=llama2
```

**常见本地服务端口:**
- Ollama: `http://localhost:11434/v1`
- LM Studio: `http://localhost:1234/v1`
- vLLM: `http://localhost:8000/v1`

---

## 添加自定义函数

### 步骤 1: 实现 Python 函数

编辑 `function_definitions.py`，添加你的函数：

```python
def send_email(to: str, subject: str, body: str) -> str:
    """
    发送邮件
    
    Args:
        to: 收件人邮箱
        subject: 邮件主题
        body: 邮件正文
    
    Returns:
        发送结果的 JSON 字符串
    """
    # 实际的邮件发送逻辑
    # import smtplib
    # ...
    
    # 这里用模拟数据
    result = {
        "success": True,
        "to": to,
        "subject": subject,
        "message": "邮件已发送"
    }
    
    return json.dumps(result, ensure_ascii=False)
```

### 步骤 2: 添加 JSON Schema 定义

在 `FUNCTION_DEFINITIONS` 列表中添加：

```python
FUNCTION_DEFINITIONS = [
    # ... 现有的函数定义 ...
    
    {
        "name": "send_email",
        "description": "发送电子邮件给指定收件人",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "收件人邮箱地址"
                },
                "subject": {
                    "type": "string",
                    "description": "邮件主题"
                },
                "body": {
                    "type": "string",
                    "description": "邮件正文内容"
                }
            },
            "required": ["to", "subject", "body"]
        }
    }
]
```

### 步骤 3: 注册函数

在 `execute_function` 中添加：

```python
def execute_function(function_name: str, arguments: dict) -> str:
    available_functions = {
        "get_weather": get_weather,
        "calculate": calculate,
        "search_database": search_database,
        "send_email": send_email,  # 添加这行
    }
    
    # ... 其余代码不变 ...
```

### 步骤 4: 测试

运行示例程序，尝试让 LLM 调用你的新函数：

```bash
python openai_example.py
```

或者在代码中测试：

```python
from llm_client import LLMClient
from function_definitions import FUNCTION_DEFINITIONS, execute_function

client = LLMClient()
response = client.chat_completion(
    messages=[{"role": "user", "content": "给 test@example.com 发一封邮件，主题是测试"}],
    functions=FUNCTION_DEFINITIONS
)
```

---

## 常见问题排查

### 问题 1: "API_KEY 未设置"

**原因:** `.env` 文件不存在或配置错误

**解决方法:**
```bash
# 检查 .env 文件是否存在
ls -la .env

# 如果不存在，复制示例文件
cp .env.example .env

# 编辑并填入正确的 API_KEY
vim .env
```

---

### 问题 2: "连接失败" 或 "401 Unauthorized"

**原因:** API Key 错误或已过期

**解决方法:**
1. 检查 API Key 是否正确复制（没有多余空格）
2. 确认 API Key 是否有效（未过期、未被撤销）
3. 检查账户余额是否充足

```bash
# 测试连接
python test_connection.py
```

---

### 问题 3: "404 Not Found"

**原因:** API_BASE_URL 或 MODEL_ID 错误

**解决方法:**
1. 检查 `API_BASE_URL` 是否正确
2. 确认 `MODEL_ID` 是否存在
3. 对于 Azure，确认使用的是部署名称而非模型名称

```bash
# OpenAI 正确的 URL
API_BASE_URL=https://api.openai.com/v1

# 注意：URL 末尾有 /v1
```

---

### 问题 4: "LLM 不调用函数"

**原因:** 函数描述不够清晰，或用户问题不明确

**解决方法:**
1. 改进函数的 `description`，使其更详细
2. 改进参数的 `description`
3. 使用更明确的用户提示

**示例:**

❌ 不好的描述:
```python
"description": "天气"
```

✅ 好的描述:
```python
"description": "获取指定城市的实时天气信息，包括温度、湿度和天气状况"
```

---

### 问题 5: "函数参数错误"

**原因:** LLM 返回的参数不符合预期

**解决方法:**
1. 在函数中添加参数验证
2. 使用 `enum` 限制参数取值
3. 提供更详细的参数描述

```python
def get_weather(city: str, unit: str = "celsius"):
    # 参数验证
    if unit not in ["celsius", "fahrenheit"]:
        return json.dumps({"error": "Invalid unit parameter"})
    
    # ... 其余逻辑
```

---

### 问题 6: "网络连接超时"

**原因:** 网络问题或 API 服务不可用

**解决方法:**
1. 检查网络连接
2. 尝试使用代理（如果在国内访问 OpenAI）
3. 检查 API 服务状态

```bash
# 测试网络连接
curl -I https://api.openai.com

# 如果需要代理
export https_proxy=http://127.0.0.1:7890
python openai_example.py
```

---

### 问题 7: "模块导入错误"

**原因:** 依赖包未安装

**解决方法:**
```bash
# 重新安装依赖
pip install -r requirements.txt

# 或者单独安装
pip install openai python-dotenv colorama
```

---

## 调试技巧

### 1. 启用详细日志

在代码中添加：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. 打印请求和响应

```python
print("发送的消息:", messages)
print("LLM 响应:", response)
print("函数调用:", function_call)
```

### 3. 使用 test_connection.py

这是最简单的测试工具：

```bash
python test_connection.py
```

### 4. 逐步测试

```bash
# 1. 先测试连接
python test_connection.py

# 2. 再测试模拟示例（不需要 API）
python simple_example.py

# 3. 最后测试真实调用
python openai_example.py
```

---

## 性能优化

### 1. 选择合适的模型

- **开发测试:** 使用 `gpt-3.5-turbo` 或 `qwen-turbo`（便宜快速）
- **生产环境:** 使用 `gpt-4` 或 `glm-4`（更准确）

### 2. 控制 token 使用

```python
response = client.chat_completion(
    messages=messages,
    functions=FUNCTION_DEFINITIONS,
    max_tokens=500,  # 限制输出长度
    temperature=0.7  # 降低随机性
)
```

### 3. 缓存函数结果

对于相同的查询，可以缓存结果：

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_weather(city: str, unit: str = "celsius"):
    # ... 函数实现
```

---

## 进阶使用

### 1. 流式输出

```python
# 在 llm_client.py 中添加流式支持
def chat_completion_stream(self, messages, functions=None):
    response = self.client.chat.completions.create(
        model=self.model_id,
        messages=messages,
        functions=functions,
        stream=True
    )
    
    for chunk in response:
        yield chunk
```

### 2. 异步调用

```python
import asyncio
from openai import AsyncOpenAI

async def async_chat():
    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(...)
    return response
```

### 3. 批量处理

```python
# 并行处理多个请求
import concurrent.futures

def process_batch(questions):
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_conversation, client, q) for q in questions]
        results = [f.result() for f in futures]
    return results
```

---

## 获取帮助

- **查看教程:** `TUTORIAL.md`
- **查看示例代码:** `openai_example.py`
- **测试连接:** `python test_connection.py`
- **GitHub Issues:** 提交问题和建议

---

## 下一步

1. ✅ 配置好 API
2. ✅ 运行示例程序
3. 📝 阅读 `TUTORIAL.md` 深入学习
4. 🔧 添加自己的函数
5. 🚀 集成到你的项目中

祝你使用愉快！🎉
