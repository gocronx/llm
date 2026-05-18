# 18 · Tool Guardrails — Agent 工具调用挡灾层

**LLM 决定调哪个工具+参数，应用执行 —— 但 LLM 拿到 write_file 想写 /etc/passwd 是常态。Guardrails 是工具和 LLM 之间的检查层：路径沙箱、危险模式拦截、严重度门禁、速率限制、审计日志。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `tools.py` | 🟢 套出去用 | 5 个示例 raw 工具（read/write/delete/shell/http） + severity 表 |
| `guardrails.py` | 🟢 套出去用 | `invoke(tool, args)` 跑所有 check → 派发 → 审计 |
| `audit.py` | 🟢 套出去用 | append-only JSONL 审计日志 |
| `main.py` | demo only | 12 个场景（4 safe + 6 danger + 2 confirm） |
| `test.py` | demo only | 9 个 guardrails 单元测试 |

## 四层防御

| 检查 | 拦什么 |
|---|---|
| 路径沙箱 (`_check_path`) | 文件工具的 path 必须在 WORKSPACE 内，禁 `..` traversal |
| 危险模式 (`_check_dangerous_args`) | `rm -rf /`、`curl | bash`、SSRF 内网 IP |
| 严重度门禁 | high-sev 工具（delete / shell）必须 `auto_confirm=True` 才能跑 |
| 速率限制 | low=30/min, medium=10/min, high=3/min；按严重度独立计数 |

每次调用都写一条 audit log（allow / block / confirm + reason）。

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py    # 9/9 passed
python main.py    # 12 个场景对照
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| guardrails 在 tool 和 LLM 之间，不是工具内部 | tool 是底层能力，guardrails 是策略；策略变了不动 tool 代码 |
| `Blocked` 异常而不是返回 None | 调用方知道是被拦了而不是 silent fail；可以选择重试 / 告诉用户 |
| 速率限制按 severity 而不是按 tool | 拦截"什么操作多 = 危险"而不是"哪个工具多" |
| `auto_confirm=True` 显式 bypass | 高危操作要求调用方明确说"我确认"，不是自动放行 |
| audit log 永远 append-only | 安全审计要求；不允许 in-place 修改/删除 |

## 常见坑

- ❌ **guardrails 写在 tool 里面** —— 加新 tool 必须重写一遍策略；解耦才是对的
- ❌ **block 用 return None** —— 调用方分不出"拦了" vs "工具失败返回空"
- ❌ **路径检查不 resolve()** —— 软链接、`/private/var` vs `/var` macOS 这种坑会绕过
- ❌ **速率限制按 tool 名** —— LLM 换个工具名（write_file vs delete_file）就绕过
- ❌ **audit 没有 reason** —— 事后追责说不清为什么 block
- ⚠️ **正则拦截不是百分百** —— 攻击者能想出新写法（`bash -c "$(curl ...)"`），需要分层防御（沙箱 + 监控 + 严重度）
