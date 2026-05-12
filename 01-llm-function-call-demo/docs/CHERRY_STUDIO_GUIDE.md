# Cherry Studio 配置指南

## 什么是 Cherry Studio？

Cherry Studio 是一个功能强大的本地 AI 客户端，支持多种大模型提供商。它提供了兼容 OpenAI 的本地 API 服务，可以让你的应用通过统一的接口访问不同的模型。

## 配置步骤

### 步骤 1: 启动 Cherry Studio 的 API 服务

1. 打开 Cherry Studio 应用
2. 进入 **设置 (Settings)**
3. 找到 **API 服务** 或 **本地服务器** 选项
4. 启用 API 服务
5. 记下服务地址（通常是 `http://localhost:7777` 或 `http://127.0.0.1:7777`）

### 步骤 2: 配置 .env 文件

编辑项目中的 `.env` 文件：

```bash
# Cherry Studio 配置
MODEL_PROVIDER=custom
API_KEY=not-needed
API_BASE_URL=http://localhost:7777/v1
MODEL_ID=gpt-4
```

**参数说明：**
- `MODEL_PROVIDER=custom` - 使用自定义提供商
- `API_KEY=not-needed` - Cherry Studio 本地服务通常不需要 API Key
- `API_BASE_URL=http://localhost:7777/v1` - Cherry Studio 的 API 地址
- `MODEL_ID=gpt-4` - 你在 Cherry Studio 中配置的模型名称

### 步骤 3: 确认模型名称

在 Cherry Studio 中查看你配置的模型名称，常见的有：

- `gpt-4` - GPT-4 模型
- `gpt-3.5-turbo` - GPT-3.5 模型
- `claude-3-opus` - Claude 3 Opus
- `qwen-turbo` - 通义千问
- `glm-4` - 智谱 GLM-4

**重要：** 将 `.env` 中的 `MODEL_ID` 改为你实际使用的模型名称。

### 步骤 4: 测试连接

```bash
python test_connection.py
```

如果看到 "✓ 连接成功！"，说明配置正确。

## 常见端口配置

Cherry Studio 可能使用不同的端口，请根据实际情况修改：

```bash
# 默认端口（最常见）
API_BASE_URL=http://localhost:7777/v1

# 其他可能的端口
API_BASE_URL=http://localhost:8000/v1
API_BASE_URL=http://localhost:1234/v1
API_BASE_URL=http://127.0.0.1:7777/v1
```

## 完整配置示例

### 示例 1: 使用 OpenAI 模型（通过 Cherry Studio）

```bash
MODEL_PROVIDER=custom
API_KEY=not-needed
API_BASE_URL=http://localhost:7777/v1
MODEL_ID=gpt-4
```

### 示例 2: 使用国内模型（通过 Cherry Studio）

```bash
MODEL_PROVIDER=custom
API_KEY=not-needed
API_BASE_URL=http://localhost:7777/v1
MODEL_ID=qwen-turbo
```

### 示例 3: 使用 Claude（通过 Cherry Studio）

```bash
MODEL_PROVIDER=custom
API_KEY=not-needed
API_BASE_URL=http://localhost:7777/v1
MODEL_ID=claude-3-opus
```

## 运行示例

配置完成后，运行示例程序：

```bash
# 1. 测试连接
python test_connection.py

# 2. 运行 Function Call 示例
python openai_example.py
```

## 故障排查

### 问题 1: "连接被拒绝" (Connection refused)

**原因：** Cherry Studio 的 API 服务未启动

**解决方法：**
1. 打开 Cherry Studio
2. 检查 API 服务是否已启动
3. 确认端口号是否正确

### 问题 2: "404 Not Found"

**原因：** API 路径或模型名称错误

**解决方法：**
1. 确认 `API_BASE_URL` 末尾有 `/v1`
2. 检查 `MODEL_ID` 是否与 Cherry Studio 中的模型名称一致
3. 在 Cherry Studio 中查看可用的模型列表

### 问题 3: "模型不支持 Function Call"

**原因：** 某些模型可能不支持 Function Calling 功能

**解决方法：**
1. 使用支持 Function Call 的模型（如 GPT-4、GPT-3.5-turbo）
2. 在 Cherry Studio 中切换到支持的模型
3. 查看模型文档确认是否支持 Function Calling

### 问题 4: 如何查看 Cherry Studio 的 API 地址？

**方法 1: 在 Cherry Studio 设置中查看**
- 打开 Cherry Studio
- 进入设置 → API 服务
- 查看服务地址和端口

**方法 2: 测试常见端口**
```bash
# 测试端口 7777
curl http://localhost:7777/v1/models

# 测试端口 8000
curl http://localhost:8000/v1/models

# 测试端口 1234
curl http://localhost:1234/v1/models
```

如果返回模型列表，说明该端口正确。

## Cherry Studio 的优势

使用 Cherry Studio 作为 API 代理的好处：

1. **统一接口** - 通过一个接口访问多个模型提供商
2. **本地管理** - 在 Cherry Studio 中统一管理 API Key
3. **切换方便** - 在 Cherry Studio 中切换模型，无需修改代码
4. **成本控制** - Cherry Studio 可以显示 API 使用情况
5. **隐私保护** - API Key 只存储在本地

## 验证配置

运行以下命令验证配置：

```bash
# 方法 1: 使用测试脚本
python test_connection.py

# 方法 2: 使用 curl 测试
curl http://localhost:7777/v1/models

# 方法 3: 使用 Python 测试
python -c "
from llm_client import LLMClient
client = LLMClient()
print('配置成功！')
"
```

## 下一步

配置成功后，你可以：

1. ✅ 运行 `python openai_example.py` 查看 Function Call 示例
2. ✅ 在 Cherry Studio 中切换不同的模型进行测试
3. ✅ 修改 `function_definitions.py` 添加自己的函数
4. ✅ 将 Function Call 集成到你的项目中

## 推荐配置

如果你在 Cherry Studio 中配置了多个模型，推荐使用以下模型进行 Function Call 测试：

**最佳选择（Function Call 支持最好）：**
- GPT-4 Turbo
- GPT-4
- GPT-3.5 Turbo

**国内模型（也支持 Function Call）：**
- 智谱 GLM-4
- 通义千问 Qwen-Turbo
- DeepSeek Chat

**注意：** 确保在 Cherry Studio 中为这些模型配置了有效的 API Key。

## 获取帮助

如果遇到问题：
1. 查看 Cherry Studio 的日志
2. 运行 `python test_connection.py` 获取详细错误信息
3. 检查 Cherry Studio 的 API 服务状态
4. 参考 `USAGE_GUIDE.md` 中的故障排查部分

祝你使用愉快！🎉
