# 本地运行支持 Function Call 的开源模型指南

## 你的配置

- **设备**: MacBook Max
- **内存**: 64GB
- **优势**: 可以运行 30B-70B 参数的模型！

---

## 推荐的开源模型

### 🥇 第一推荐：Hermes 2 Pro (Mistral/Llama 微调版)

**最佳选择！专门为 Function Call 优化**

#### 模型信息
- **基础模型**: Mistral 7B / Llama 3 8B
- **参数规模**: 7B-8B
- **内存需求**: 8-12GB
- **Function Call 支持**: ⭐⭐⭐⭐⭐ 原生支持
- **开发者**: NousResearch

#### 可用版本
1. **Hermes-2-Pro-Mistral-7B** (推荐)
   - 基于 Mistral 7B
   - Function Call 效果最好
   - 速度快

2. **Hermes-2-Pro-Llama-3-8B**
   - 基于 Llama 3
   - 更新，性能更好

#### 如何使用

**方法 1: 使用 Ollama（最简单）**

```bash
# 1. 安装 Ollama
brew install ollama

# 2. 下载模型
ollama pull adrienbrault/nous-hermes2pro:Q8_0

# 3. 运行模型
ollama serve

# 4. 测试
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "adrienbrault/nous-hermes2pro:Q8_0",
    "messages": [{"role": "user", "content": "北京天气怎么样？"}],
    "tools": [...]
  }'
```

**方法 2: 使用 LM Studio**

1. 下载 LM Studio: https://lmstudio.ai/
2. 搜索 "Hermes-2-Pro"
3. 下载并加载模型
4. 启动本地服务器（兼容 OpenAI API）

---

### 🥈 第二推荐：Functionary

**专门为 Function Call 设计的模型**

#### 模型信息
- **基础模型**: Llama 2 / Llama 3
- **参数规模**: 7B-70B
- **内存需求**: 
  - 7B: 8-12GB
  - 13B: 16-20GB
  - 70B: 40-50GB ✓ 你可以跑！
- **Function Call 支持**: ⭐⭐⭐⭐⭐ 专门优化
- **开发者**: MeetKai

#### 可用版本
1. **functionary-small-v2.5** (7B) - 快速
2. **functionary-medium-v2.5** (13B) - 平衡
3. **functionary-large-v2.5** (70B) - 最强 ✓ 推荐你用这个！

#### 如何使用

```bash
# 使用 Ollama
ollama pull meetkai/functionary-small-v2.5

# 或下载 70B 版本（你的配置可以跑）
ollama pull meetkai/functionary-large-v2.5
```

---

### 🥉 第三推荐：Llama 3.1 (官方支持)

**Meta 官方支持 Function Call**

#### 模型信息
- **开发者**: Meta
- **参数规模**: 8B / 70B / 405B
- **内存需求**:
  - 8B: 8-12GB
  - 70B: 40-50GB ✓ 你可以跑！
- **Function Call 支持**: ⭐⭐⭐⭐ 官方支持
- **发布时间**: 2024年7月

#### 可用版本
1. **Llama-3.1-8B-Instruct** - 快速
2. **Llama-3.1-70B-Instruct** - 强大 ✓ 推荐

#### 如何使用

```bash
# 使用 Ollama
ollama pull llama3.1:8b
ollama pull llama3.1:70b  # 你的配置可以跑
```

---

### 🌟 第四推荐：Gorilla OpenFunctions

**专门训练的 API 调用模型**

#### 模型信息
- **基础模型**: Llama 2
- **参数规模**: 7B
- **内存需求**: 8-12GB
- **Function Call 支持**: ⭐⭐⭐⭐ 专门训练
- **开发者**: UC Berkeley

#### 特点
- 专门为 API 调用优化
- 支持 1600+ API
- 准确率高

#### 如何使用

```bash
# 使用 Ollama
ollama pull gorilla-openfunctions-v2
```

---

## 详细对比

| 模型 | 参数 | 内存 | Function Call | 速度 | 推荐度 |
|------|------|------|---------------|------|--------|
| **Hermes-2-Pro-Mistral** | 7B | 8GB | ⭐⭐⭐⭐⭐ | 快 | ⭐⭐⭐⭐⭐ |
| **Functionary-70B** | 70B | 45GB | ⭐⭐⭐⭐⭐ | 中 | ⭐⭐⭐⭐⭐ |
| **Llama-3.1-70B** | 70B | 45GB | ⭐⭐⭐⭐ | 中 | ⭐⭐⭐⭐ |
| **Gorilla** | 7B | 8GB | ⭐⭐⭐⭐ | 快 | ⭐⭐⭐⭐ |

---

## 推荐方案

### 方案 1: 快速开始（推荐）

**使用 Hermes-2-Pro-Mistral-7B**

```bash
# 1. 安装 Ollama
brew install ollama

# 2. 下载模型
ollama pull adrienbrault/nous-hermes2pro:Q8_0

# 3. 启动服务
ollama serve
```

**优点:**
- 快速（7B 模型）
- Function Call 效果好
- 内存占用小（8GB）
- 响应快

### 方案 2: 最强性能

**使用 Functionary-70B**

```bash
# 下载 70B 模型（充分利用你的 64GB 内存）
ollama pull meetkai/functionary-large-v2.5
```

**优点:**
- 最强的 Function Call 能力
- 充分利用你的硬件
- 准确率最高

**缺点:**
- 速度较慢
- 内存占用大

### 方案 3: 平衡方案

**使用 Llama-3.1-8B**

```bash
ollama pull llama3.1:8b
```

**优点:**
- Meta 官方支持
- 性能好
- 社区支持好

---

## 完整安装步骤

### 步骤 1: 安装 Ollama

```bash
# 使用 Homebrew 安装
brew install ollama

# 或者从官网下载
# https://ollama.ai/download
```

### 步骤 2: 下载模型

```bash
# 推荐：Hermes-2-Pro（快速开始）
ollama pull adrienbrault/nous-hermes2pro:Q8_0

# 或者：Functionary-70B（最强性能）
ollama pull meetkai/functionary-large-v2.5

# 或者：Llama 3.1
ollama pull llama3.1:8b
```

### 步骤 3: 启动服务

```bash
# 启动 Ollama 服务（兼容 OpenAI API）
ollama serve

# 服务会运行在 http://localhost:11434
```

### 步骤 4: 配置我们的项目

编辑 `.env` 文件：

```bash
MODEL_PROVIDER=custom
API_KEY=not-needed
API_BASE_URL=http://localhost:11434/v1
MODEL_ID=adrienbrault/nous-hermes2pro:Q8_0
```

### 步骤 5: 测试

```bash
# 测试连接
python test_connection.py

# 运行 Function Call 示例
python openai_example.py
```

---

## 使用 LM Studio（图形界面）

如果你喜欢图形界面：

### 步骤 1: 下载 LM Studio

https://lmstudio.ai/

### 步骤 2: 搜索并下载模型

在 LM Studio 中搜索：
- "Hermes-2-Pro"
- "Functionary"
- "Llama-3.1"

### 步骤 3: 启动本地服务器

1. 加载模型
2. 点击 "Start Server"
3. 默认运行在 `http://localhost:1234`

### 步骤 4: 配置项目

```bash
MODEL_PROVIDER=custom
API_KEY=not-needed
API_BASE_URL=http://localhost:1234/v1
MODEL_ID=hermes-2-pro-mistral-7b
```

---

## 性能对比

### 在你的 MacBook Max 64GB 上

| 模型 | 加载时间 | 推理速度 | 内存占用 | 可行性 |
|------|---------|---------|---------|--------|
| 7B 模型 | 5-10秒 | 30-50 tokens/s | 8-12GB | ✅ 完美 |
| 13B 模型 | 10-20秒 | 20-30 tokens/s | 16-20GB | ✅ 很好 |
| 70B 模型 | 30-60秒 | 5-10 tokens/s | 45-50GB | ✅ 可行 |

**建议:**
- **日常使用**: 7B 模型（快速）
- **重要任务**: 70B 模型（准确）

---

## Function Call 格式

这些模型大多支持 OpenAI 兼容的格式：

```python
{
    "model": "hermes-2-pro",
    "messages": [...],
    "tools": [  # 注意：使用 tools 格式
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "获取天气",
                "parameters": {...}
            }
        }
    ]
}
```

我们的 `llm_client.py` 已经支持这个格式！

---

## 实际测试

### 测试 Hermes-2-Pro

```bash
# 1. 启动 Ollama
ollama serve

# 2. 在另一个终端运行
python test_connection.py
```

预期结果：
```
✓ 连接成功！
✓ 模型支持 Function Call
```

---

## 常见问题

### Q1: 70B 模型会不会太慢？

**A:** 在你的配置上：
- 加载时间：30-60秒
- 推理速度：5-10 tokens/秒
- 可以接受，但不如 7B 快

### Q2: 推荐哪个模型？

**A:** 
- **快速开始**: Hermes-2-Pro-7B
- **最佳效果**: Functionary-70B
- **官方支持**: Llama-3.1-70B

### Q3: 如何切换模型？

**A:** 只需修改 `.env` 文件中的 `MODEL_ID`

### Q4: 可以同时运行多个模型吗？

**A:** 可以，但注意内存：
- 7B + 7B = 16-24GB ✓
- 7B + 70B = 53-62GB ✓ 刚好
- 70B + 70B = 90-100GB ✗ 超出

---

## 推荐的学习路径

1. **先用 Hermes-2-Pro-7B** - 快速体验
2. **测试 Function Call** - 运行我们的示例
3. **尝试 70B 模型** - 体验更强性能
4. **对比效果** - 选择最适合你的

---

## 资源链接

- [Ollama 官网](https://ollama.ai/)
- [LM Studio](https://lmstudio.ai/)
- [Hermes-2-Pro](https://huggingface.co/NousResearch/Hermes-2-Pro-Mistral-7B)
- [Functionary](https://github.com/MeetKai/functionary)
- [Llama 3.1](https://ai.meta.com/blog/meta-llama-3-1/)
- [Gorilla](https://github.com/ShishirPatil/gorilla)

---

## 总结

### ✅ 你的 MacBook Max 64GB 可以运行：

1. **所有 7B-13B 模型** - 完美运行
2. **70B 模型** - 可以运行，速度可接受
3. **多个小模型同时运行** - 没问题

### 🎯 推荐配置：

**快速开始:**
```bash
ollama pull adrienbrault/nous-hermes2pro:Q8_0
```

**最强性能:**
```bash
ollama pull meetkai/functionary-large-v2.5
```

### 🚀 下一步：

1. 安装 Ollama
2. 下载推荐模型
3. 配置我们的项目
4. 开始使用本地 Function Call！

你的配置非常适合运行本地大模型！🎉
