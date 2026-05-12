# Streaming 演示

流式输出是生产环境的必需功能，极大提升用户体验。

**三语言实现：Python、Go、Rust**

## 为什么需要 Streaming

### 用户体验对比

**非流式输出：**
```
用户提问 → [等待 5-10 秒] → 完整答案出现
```
- ❌ 用户感觉很慢
- ❌ 不知道是否在处理
- ❌ 可能以为卡住了

**流式输出：**
```
用户提问 → [0.5-1 秒] → 开始逐字显示 → 持续输出
```
- ✅ 立即有反馈
- ✅ 用户感觉很快
- ✅ 知道正在处理

### 实际数据

| 指标 | 非流式 | 流式 | 差异 |
|------|--------|------|------|
| 首字时间 | 5-10秒 | 0.5-1秒 | **快 5-10倍** |
| 用户感知 | 慢 | 快 | **体验提升巨大** |
| 实际总时间 | 10秒 | 10秒 | 相同 |

**结论：总时间相同，但用户感觉完全不同！**

---

## 快速开始

### Python 版本

```bash
cd python
pip install -r requirements.txt

# 1. 基础对比演示
python basic_streaming.py

# 2. 流式 Function Call
python streaming_with_function_call.py

# 3. Web 演示
python web_demo.py
# 访问 http://localhost:8001
```

### Go 版本

```bash
cd go
go mod tidy

# 基础对比演示
go run basic_streaming.go
```

### Rust 版本

```bash
cd rust
cargo build --release

# 基础对比演示
cargo run --release
```

---

## 核心技术

### 1. SSE (Server-Sent Events)

**什么是 SSE：**
- 服务器向客户端推送数据的标准协议
- 单向通信（服务器 → 客户端）
- 基于 HTTP，简单易用

**格式：**
```
data: {"content": "你"}
data: {"content": "好"}
data: {"content": "！"}
data: [DONE]
```

**优点：**
- ✅ 标准协议，浏览器原生支持
- ✅ 自动重连
- ✅ 简单易实现

**缺点：**
- ❌ 只能服务器推送
- ❌ 不支持二进制数据

---

### 2. 流式实现

**Python 实现：**
```python
import requests

response = requests.post(
    url,
    json={
        "model": "...",
        "messages": [...],
        "stream": True  # 关键：启用流式
    },
    stream=True  # 关键：requests 流式
)

for line in response.iter_lines():
    if line:
        # 处理每一行数据
        data = line.decode('utf-8')
        if data.startswith('data: '):
            chunk = json.loads(data[6:])
            content = chunk['choices'][0]['delta']['content']
            print(content, end='', flush=True)
```

**关键点：**
1. API 请求设置 `"stream": True`
2. requests 设置 `stream=True`
3. 使用 `iter_lines()` 逐行读取
4. 解析 SSE 格式（`data: ...`）
5. 立即输出（`flush=True`）

---

### 3. Web 实现

**后端（FastAPI）：**
```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

@app.post('/stream')
async def stream(request: Request):
    async def generate():
        # 调用 LLM API（流式）
        for chunk in llm_stream():
            yield f"data: {json.dumps(chunk)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type='text/event-stream'
    )
```

**前端（JavaScript）：**
```javascript
const response = await fetch('/stream', {
    method: 'POST',
    body: JSON.stringify({ prompt: '...' })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    // 解析并显示
    displayChunk(chunk);
}
```

---

## 流式 Function Call

### 挑战

**问题：**
- 工具调用信息是分块传输的
- `function.name` 可能分多次
- `function.arguments` 肯定分多次
- 需要累积完整信息

**示例：**
```
Chunk 1: {"tool_calls": [{"index": 0, "function": {"name": "get"}}]}
Chunk 2: {"tool_calls": [{"index": 0, "function": {"name": "_weather"}}]}
Chunk 3: {"tool_calls": [{"index": 0, "function": {"arguments": "{\"city"}}]}
Chunk 4: {"tool_calls": [{"index": 0, "function": {"arguments": "\": \"北京\"}"}}]}
```

### 解决方案

```python
tool_calls = []

for chunk in stream:
    if 'tool_calls' in delta:
        for tc in delta['tool_calls']:
            index = tc['index']
            
            # 初始化
            if index >= len(tool_calls):
                tool_calls.append({
                    'function': {'name': '', 'arguments': ''}
                })
            
            # 累积信息
            if 'function' in tc:
                if 'name' in tc['function']:
                    tool_calls[index]['function']['name'] += tc['function']['name']
                if 'arguments' in tc['function']:
                    tool_calls[index]['function']['arguments'] += tc['function']['arguments']

# 完整的工具调用信息
function_name = tool_calls[0]['function']['name']
arguments = json.loads(tool_calls[0]['function']['arguments'])
```

---

## 最佳实践

### 1. 用户体验

**显示进度：**
```
🤖 思考中...
🔧 调用工具: get_weather
   参数: {"city": "北京"}
   结果: {"temperature": 15}
🤖 回答: [流式显示]
```

**加载动画：**
- 显示 "生成中..."
- 显示加载动画
- 禁用发送按钮

### 2. 错误处理

```python
try:
    for chunk in stream:
        # 处理 chunk
        pass
except requests.exceptions.Timeout:
    print("请求超时")
except requests.exceptions.ConnectionError:
    print("连接失败")
except Exception as e:
    print(f"错误: {e}")
```

### 3. 性能优化

**缓冲：**
```python
buffer = []
for chunk in stream:
    buffer.append(chunk)
    
    # 每 10 个 chunk 刷新一次
    if len(buffer) >= 10:
        display(''.join(buffer))
        buffer = []
```

**原因：**
- 减少 UI 更新次数
- 提高性能
- 但会稍微延迟显示

---

## 常见问题

### Q: Streaming 会增加成本吗？

A: 不会。Token 数量相同，成本相同。

### Q: Streaming 会更慢吗？

A: 总时间相同，但用户感觉更快。

### Q: 所有场景都需要 Streaming 吗？

A: 
- ✅ 用户界面 → 必须用
- ✅ 长文本生成 → 必须用
- ❌ 后台任务 → 可以不用
- ❌ 批量处理 → 可以不用

### Q: Streaming 实现复杂吗？

A: 稍微复杂，但值得：
- 非流式：10 行代码
- 流式：30 行代码
- 用户体验提升：巨大

---

## 技术对比

### SSE vs WebSocket

| 特性 | SSE | WebSocket |
|------|-----|-----------|
| 方向 | 单向（服务器→客户端） | 双向 |
| 协议 | HTTP | WebSocket |
| 实现 | 简单 | 复杂 |
| 重连 | 自动 | 需要手动 |
| 适用 | LLM 流式输出 | 实时聊天 |

**结论：LLM 流式输出用 SSE 就够了。**

---

### 流式 vs 非流式

| 指标 | 非流式 | 流式 |
|------|--------|------|
| 实现复杂度 | ⭐ | ⭐⭐⭐ |
| 用户体验 | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 首字时间 | 5-10秒 | 0.5-1秒 |
| 总时间 | 10秒 | 10秒 |
| 成本 | 相同 | 相同 |

**结论：实现稍复杂，但用户体验提升巨大。**

---

## 核心要点

> **Streaming 是生产环境的必需功能，不是可选项。**

**关键数据：**
- 首字时间：5-10秒 → 0.5-1秒（快 5-10倍）
- 用户感知：慢 → 快（体验提升巨大）
- 实现成本：30 行代码
- Token 成本：相同

**记住：**
1. 所有面向用户的 LLM 应用都应该用 Streaming
2. 用户体验差异巨大
3. 实现成本很低
4. 没有理由不用

---

## 实际应用

### ChatGPT
- ✅ 使用 Streaming
- 用户感觉很快

### Claude
- ✅ 使用 Streaming
- 用户感觉很快

### 你的应用
- ❓ 如果不用 Streaming
- 用户会觉得很慢
- 体验远不如竞品

**结论：Streaming 是标配，不是加分项。**
