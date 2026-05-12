# MCP (Model Context Protocol) 演示

MCP 是 Anthropic 推出的标准协议，让 LLM 能够以标准化的方式连接各种数据源和工具。

**核心价值：标准化、可复用、长期价值高**

**三语言实现：Python、Go、Rust**

---

## 什么是 MCP

### 简单理解

**Function Call（传统方式）：**
```
每个应用自己定义工具 → 重复劳动 → 生态碎片化
```

**MCP（标准化方式）：**
```
MCP Server 定义工具 → 多个应用复用 → 生态健康
```

### 核心概念

**MCP Server：**
- 提供工具的服务器
- 定义工具的接口和实现
- 可以被多个 Client 复用

**MCP Client：**
- 连接 MCP Server
- 调用 Server 提供的工具
- 通过 LLM 智能使用工具

**MCP Protocol：**
- 统一的通信协议
- 基于 JSON-RPC
- 标准化的工具定义格式

---

## 快速开始

### Python 版本

```bash
cd python
pip install -r requirements.txt

# 1. 对比演示
python compare.py

# 2. MCP Client 演示
python client/mcp_client.py
```

### Go 版本

```bash
cd go
go mod tidy

# MCP Client 演示
go run mcp_client.go
```

### Rust 版本

```bash
cd rust
cargo build --release

# MCP Client 演示
cargo run --release
```

---

## MCP vs Function Call

### 架构对比

| 特性 | Function Call | MCP |
|------|--------------|-----|
| 工具定义 | 每个应用自己定义 | Server 定义一次 |
| 复用性 | 难以复用 | 易于复用 |
| 标准化 | 没有标准 | 统一标准 |
| 生态 | 碎片化 | 健康 |
| 复杂度 | 简单 | 稍复杂 |

### 代码对比

**Function Call：**
```python
# 每个应用都要定义
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件",
            "parameters": {...}
        }
    }
]

# 每个应用都要实现
def read_file(path):
    with open(path) as f:
        return f.read()
```

**MCP：**
```python
# MCP Server 定义一次
@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="read_file",
            description="读取文件",
            inputSchema={...}
        )
    ]

# 所有 Client 都可以使用
client.connect("filesystem-server")
result = client.call_tool("read_file", {"path": "file.txt"})
```

---

## MCP Server 示例

### 文件系统 Server

提供文件操作功能：

**工具列表：**
- `read_file` - 读取文件内容
- `write_file` - 写入文件内容
- `list_directory` - 列出目录内容
- `file_exists` - 检查文件是否存在

**安全特性：**
- 路径验证（防止访问基础路径外的文件）
- 错误处理
- 权限控制

**实现：**
```python
class FileSystemServer:
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.server = Server("filesystem-server")
    
    @server.list_tools()
    async def list_tools():
        return [...]
    
    @server.call_tool()
    async def call_tool(name, arguments):
        if name == "read_file":
            return await self._read_file(arguments["path"])
        # ...
```

---

## MCP Client 示例

### 基础用法

```python
from mcp_client import SimpleMCPClient

# 创建 Client
client = SimpleMCPClient()

# 注册工具
client.register_tool(tool_definition, handler)

# 与 LLM 对话（自动调用工具）
messages = [{"role": "user", "content": "创建一个 todo.txt 文件"}]
result = client.chat(messages)
```

### 工作流程

1. 用户发送请求
2. LLM 决定调用哪个工具
3. Client 调用 MCP Server 的工具
4. 工具返回结果
5. LLM 基于结果生成回答

---

## 现有 MCP Servers

### Anthropic 官方

- **filesystem** - 文件系统操作
- **sqlite** - SQLite 数据库
- **fetch** - HTTP 请求
- **github** - GitHub API
- **google-drive** - Google Drive
- **brave-search** - Brave 搜索

### 社区贡献

- **postgresql** - PostgreSQL 数据库
- **mongodb** - MongoDB 数据库
- **gmail** - Gmail API
- **notion** - Notion API
- **slack** - Slack API
- **更多...**

**查找更多：** https://github.com/modelcontextprotocol

---

## 实战场景

### 1. 文件管理助手

```
用户: "帮我整理项目文件，把所有 .py 文件移到 src/ 目录"
AI: 
  1. 调用 list_directory 列出文件
  2. 调用 read_file 读取每个 .py 文件
  3. 调用 write_file 写入到 src/ 目录
  4. 返回整理结果
```

### 2. 代码审查助手

```
用户: "审查 main.py 的代码质量"
AI:
  1. 调用 read_file 读取 main.py
  2. 分析代码（安全、性能、风格）
  3. 调用 write_file 生成审查报告
  4. 返回审查结果
```

### 3. 数据分析助手

```
用户: "分析 data.csv 并生成报告"
AI:
  1. 调用 read_file 读取 data.csv
  2. 分析数据
  3. 调用 write_file 生成报告
  4. 返回分析结果
```

---

## MCP 的优势

### 1. 标准化

- 统一的协议
- 统一的工具定义格式
- 统一的错误处理

### 2. 可复用

- Server 可以被多个 Client 使用
- 减少重复开发
- 提高开发效率

### 3. 生态健康

- 社区可以贡献 Server
- 应用可以直接使用现有 Server
- 生态系统良性循环

### 4. 安全性

- 统一的安全标准
- 权限控制
- 审计日志

### 5. 长期价值

- Anthropic 大力推广
- 行业标准趋势
- 不会过时

---

## MCP vs 其他方案

### MCP vs Function Call

| 特性 | Function Call | MCP |
|------|--------------|-----|
| 标准化 | ❌ | ✅ |
| 复用性 | ❌ | ✅ |
| 简单性 | ✅ | ⚠️ |
| 适用场景 | 简单工具 | 通用工具 |

### MCP vs LangChain Tools

| 特性 | LangChain Tools | MCP |
|------|----------------|-----|
| 标准化 | ⚠️ 框架特定 | ✅ 协议标准 |
| 独立性 | ❌ 依赖框架 | ✅ 独立协议 |
| 生态 | ⚠️ 框架生态 | ✅ 开放生态 |

### MCP vs Plugin 系统

| 特性 | Plugin | MCP |
|------|--------|-----|
| 标准化 | ⚠️ 各自标准 | ✅ 统一标准 |
| 互操作性 | ❌ | ✅ |
| 学习成本 | ⚠️ 每个不同 | ✅ 学一次 |

---

## 最佳实践

### 1. Server 设计

**单一职责：**
```python
# ✅ 好：专注文件系统
FileSystemServer

# ❌ 差：什么都做
UniversalServer
```

**安全第一：**
```python
# ✅ 好：验证路径
def _get_full_path(self, path):
    full_path = os.path.abspath(os.path.join(self.base_path, path))
    if not full_path.startswith(self.base_path):
        raise ValueError("路径超出范围")
    return full_path

# ❌ 差：直接使用
def read_file(self, path):
    with open(path) as f:  # 危险！
        return f.read()
```

**错误处理：**
```python
# ✅ 好：友好的错误信息
try:
    result = do_something()
except FileNotFoundError:
    return "文件不存在"
except PermissionError:
    return "没有权限"

# ❌ 差：直接抛出异常
result = do_something()  # 可能崩溃
```

### 2. Client 使用

**工具选择：**
```python
# ✅ 好：让 LLM 决定
result = client.chat(messages)

# ❌ 差：硬编码工具调用
result = client.call_tool("read_file", {...})
```

**错误重试：**
```python
# ✅ 好：自动重试
for attempt in range(3):
    try:
        result = client.call_tool(...)
        break
    except Exception as e:
        if attempt == 2:
            raise
        time.sleep(1)
```

### 3. 工具设计

**清晰的描述：**
```python
# ✅ 好：详细描述
Tool(
    name="read_file",
    description="读取指定路径的文件内容。路径相对于工作目录。",
    inputSchema={...}
)

# ❌ 差：模糊描述
Tool(
    name="read_file",
    description="读文件",
    inputSchema={...}
)
```

**合理的参数：**
```python
# ✅ 好：必需参数 + 可选参数
{
    "type": "object",
    "properties": {
        "path": {"type": "string"},  # 必需
        "encoding": {"type": "string", "default": "utf-8"}  # 可选
    },
    "required": ["path"]
}

# ❌ 差：所有参数都必需
{
    "required": ["path", "encoding", "mode", "buffering", ...]
}
```

---

## 常见问题

### Q: MCP 会取代 Function Call 吗？

A: 不会完全取代，各有适用场景：
- 简单工具 → Function Call
- 通用工具 → MCP
- 生产环境 → 优先 MCP

### Q: MCP 复杂吗？

A: 稍微复杂，但值得：
- 学习成本：1-2 天
- 长期收益：巨大
- 一次学习，终身受益

### Q: 如何选择 MCP Server？

A: 优先使用现有的：
1. 检查官方 Server
2. 检查社区 Server
3. 实在没有再自己写

### Q: MCP 的性能如何？

A: 性能很好：
- 基于 JSON-RPC（轻量）
- 支持流式传输
- 支持批量操作

### Q: MCP 安全吗？

A: 需要注意：
- Server 要做好权限控制
- 验证所有输入
- 记录审计日志
- 使用 HTTPS（生产环境）

---

## 学习路径

### 1. 基础（1 天）

- 理解 MCP 概念
- 运行示例代码
- 对比 Function Call

### 2. 进阶（2-3 天）

- 实现自己的 MCP Server
- 集成到应用中
- 学习最佳实践

### 3. 高级（1 周）

- 研究现有 Server 源码
- 贡献社区 Server
- 生产环境部署

---

## 资源链接

**官方资源：**
- MCP 规范：https://spec.modelcontextprotocol.io/
- GitHub：https://github.com/modelcontextprotocol
- 文档：https://modelcontextprotocol.io/

**社区资源：**
- MCP Servers 列表：https://github.com/modelcontextprotocol/servers
- 示例代码：https://github.com/modelcontextprotocol/examples

---

## 总结

### MCP 的核心价值

1. **标准化** - 统一的协议和格式
2. **可复用** - Server 可以被多个应用使用
3. **生态健康** - 社区可以贡献和复用
4. **长期价值** - 不会过时的技术

### 何时使用 MCP

✅ **适合：**
- 通用工具（文件、数据库、API）
- 需要在多个应用中复用
- 生产环境
- 长期项目

❌ **不适合：**
- 一次性工具
- 应用特定逻辑
- 快速原型
- 简单场景

### 学习建议

1. 先学 Function Call（基础）
2. 再学 MCP（进阶）
3. 根据场景选择合适方案
4. 关注 MCP 生态发展

---

**记住：MCP 是 Function Call 的标准化演进，长期价值更高。**
