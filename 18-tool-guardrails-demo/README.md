# 18 · Tool Guardrails Demo

Agent 工具调用前的挡灾层。LLM 想调 `write_file` 写 `/etc/passwd` 是常态 —— guardrails 是工具和 LLM 之间的检查关卡。

## 四层防御

| 层 | 拦什么 |
|---|---|
| 路径沙箱 | 文件操作 path 必须在 WORKSPACE 内 |
| 危险模式 | rm -rf /、curl \| bash、SSRF 内网 IP |
| 严重度门禁 | high-sev 工具要 `auto_confirm=True` |
| 速率限制 | 按 severity 独立计数（low 30/min, high 3/min） |

每次调用都写一条 audit log（allow / block / confirm）。

## 跑起来

```bash
cd python
pip install -r requirements.txt
python test.py    # 9/9 passed
python main.py    # 12 个场景
```

## 共通的坑

- ❌ guardrails 写在 tool 里 → 加 tool 重写策略
- ❌ block 用 return None → 调用方分不出失败 vs 拦截
- ❌ 路径不 resolve() → 软链接绕过
- ❌ 速率按 tool 名 → 换名字就绕过
- ⚠️ 正则拦不全 → 需要分层防御
