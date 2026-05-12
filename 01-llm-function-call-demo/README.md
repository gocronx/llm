# LLM Function Call Demo

Function Call（函数调用）多语言完整演示项目。

## 📁 项目结构

```
01-llm-function-call-demo/
├── .env                    # 共享配置文件
├── README.md              # 本文件
├── python/                # Python 实现
│   ├── demo.py
│   ├── test.py
│   ├── function_definitions.py
│   └── requirements.txt
├── go/                    # Go 实现
│   ├── demo.go
│   ├── test.go
│   ├── functions.go
│   └── go.mod
├── rust/                  # Rust 实现
│   ├── src/
│   │   ├── main.rs       (demo)
│   │   ├── test.rs
│   │   └── functions.rs
│   └── Cargo.toml
├── docs/                  # 详细文档
└── archive/               # 历史示例
```

## ⚙️ 配置环境变量

编辑 `.env` 文件，配置你的 API 信息：

```bash
API_BASE_URL=http://localhost:8000/v1
API_KEY=Baron@123321
MODEL_ID=Qwen3.5-27B-Claude-4.6-Opus-Distilled-MLX-4bit
```

---

## 🐍 Python 版本

### 安装依赖

```bash
cd python
pip install -r requirements.txt
```

### 运行测试

```bash
python test.py
```

### 运行演示

```bash
python demo.py
```

---

## 🔷 Go 版本

### 安装依赖

```bash
cd go
go mod download
```

### 运行测试

```bash
go run test.go functions.go
```

### 运行演示

```bash
go run demo.go functions.go
```

---

## 🦀 Rust 版本

### 运行演示

```bash
cd rust
cargo run --bin demo
```

### 运行测试

```bash
cargo run --bin test
```

---

## 📝 示例函数

所有语言版本都实现了相同的三个函数：

1. **get_weather** - 获取天气信息
2. **calculate** - 数学计算
3. **search_database** - 数据库搜索

## 📄 文件说明

### 每个语言版本包含：

- **demo** - 完整演示（包含函数执行和最终回答）
- **test** - 快速测试（验证模型是否支持 Function Call）
- **functions** - 函数定义和实现

## 💡 核心概念

### Function Call 流程

```
用户问题 → LLM 分析 → 决定调用函数 → 执行函数 → LLM 生成回答
```

### 两轮对话

1. **第一轮**：发送用户问题 + 函数定义 → LLM 返回要调用的函数
2. **第二轮**：发送函数执行结果 → LLM 生成自然语言回答

## ✨ 特点

- ✅ 多语言：Python、Go、Rust 三种实现
- ✅ 简洁：只保留核心代码
- ✅ 实用：直接可用的演示
- ✅ 易扩展：轻松添加自定义函数
