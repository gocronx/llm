# 01 · LLM Function Call (Go) — `go-openai` + 两轮往返

**Go 版 slim：使用 `sashabaranov/go-openai` 替代手撸 `net/http`，工具注册表 + 两轮交互一共 304 行（原版 633 行）。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `client.go` | 🟢 套出去用 | `Run()` 一次完成两轮交互 |
| `tools.go` | 🟢 套出去用（自己改） | `register(name, desc, schema, fn)`；schema 和实现一起注册 |
| `main.go` | demo + verify | 默认跑 demo；`go run . verify` 跑工具调用验证 |

## 怎么跑

```bash
cd go_slim
go mod tidy
go run .            # demo
go run . verify     # 验证调对了工具
```

**⚠️ 必须用 `go run .`，不是 `go run main.go`** —— Go 的 main package 由整个目录里所有 `.go` 文件组成，单文件运行会因为找不到 `Run` / `schemas`（在另外两个文件里）而编译失败。

## 行数对比

| 文件 | 原版 | slim |
|---|---|---|
| 工具定义 | `functions.go` 351 | `tools.go` 164 |
| 主入口 | `demo.go` 147 | `main.go` 86 + `client.go` 54 |
| 测试 | `test.go` 135 | （并到 `main.go verify`） |
| **总计** | **633** | **304** |

砍掉的：
- 手撸 `contains` / `containsMiddle`（functions.go:338-351）—— `strings.Contains` 一行解决
- `parsePriceQuery` 在 query 里用循环扫数字 + 字符串匹配"以上/以下" —— 改成让 LLM 自己拆参数
- demo 和 test 各自重复一遍 `http.NewRequest` + JSON 序列化
- 原版 demo.go 和 test.go 都声明了 `func main()`，在同一个 package 里其实编译不过；slim 用一个 main 里的子命令路由解决

## 关键设计点

| 决策 | 原因 |
|---|---|
| `cfg.HTTPClient = &http.Client{Transport: &http.Transport{Proxy: nil}}` | Go 默认 `http.ProxyFromEnvironment` 会读 `HTTP_PROXY`，本地 MLX 场景走代理只会失败。预防性关掉 |
| `register()` + `init()` 注册 | Go 没有装饰器，用 init 函数 + 函数变量做注册表，schema 和实现绑定 |
| `for _, tc := range msg.ToolCalls` 全跑完 | 同 Python 版：LLM 可能一次返回多个 tool_calls，全跑完再回 LLM |
| `messages = append(messages, msg)` | go-openai 的 `ChatCompletionMessage` 已经是值类型，直接 append 就能正确序列化回去 |

## 加新工具

在 `tools.go` 的 `init()` 里加一个 `register(...)`：

```go
register("send_email", "发邮件",
    jsonschema.Definition{
        Type: jsonschema.Object,
        Properties: map[string]jsonschema.Definition{
            "to":      {Type: jsonschema.String},
            "subject": {Type: jsonschema.String},
            "body":    {Type: jsonschema.String},
        },
        Required: []string{"to", "subject", "body"},
    },
    func(args map[string]any) any {
        // ... 实际发邮件
        return map[string]any{"sent": true}
    },
)
```

`main.go` / `client.go` 一行都不改。

## 常见坑

- ⚠️ **`go run main.go` 编译失败** —— 用 `go run .`，详见上面
- ⚠️ **HTTP_PROXY 环境变量** —— Go 的 `net/http` 默认读 `HTTP_PROXY` 但不读 macOS 系统代理。如果你 shell 里 export 了代理变量，本 demo 已经显式 `Proxy: nil` 绕过
- ❌ **`msg.ToolCalls` 只用 `[0]`** —— LLM 可能并行调多个工具
- ❌ **不把 assistant message 回灌** —— 第二轮 LLM 看不到自己刚才决定调啥工具
