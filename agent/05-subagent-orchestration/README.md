# 05 · Subagent 编排

主 agent 把任务拆给多个 **subagent 并行执行**, 再聚合结果. 比单 agent 干一切快、context 干净.

灵感:
- [Claude Code](https://docs.anthropic.com/claude-code) 的 `Task` tool (`subagent_type` 参数)
- PraisonAI / AutoGPT 的 multi-agent 模式
- [Anthropic Multi-Agent Research](https://www.anthropic.com/research/multi-agent)

## 单 agent 的局限

一个 agent 干一切的痛点:

1. **Context 污染** — 调研 task A 时塞满 A 信息, 切到 B 必须切 context, LLM 答非所问
2. **顺序执行** — A → B → C 串行, 时间是 sum
3. **Scope creep** — 一个 prompt 想干 5 件事, LLM 容易忘前面的 instruction
4. **失败放大** — 任一步崩, 整个 agent 死, 不能继续别的

## Subagent 编排怎么解

```
   主 Agent (Orchestrator)
   ├── delegate("researcher", "find competitors")    ──┐
   ├── delegate("researcher", "find pricing")        ──┼─ asyncio.gather
   ├── delegate("analyst", "summarize Q3 reports")   ──┘
   └── 聚合 3 个 summary, 给用户最终答案

   每个 subagent:
   - 自己的 messages 历史 (跟其他 agent 隔离)
   - 自己的 tools 限制 (researcher 只能 web_search, analyst 只能 read_file)
   - 完成后**只返回 summary**, 不返回完整 messages
```

| 解 | 怎么解 |
|----|--------|
| Context 污染 | 每 subagent 独立 messages, 主 agent 只见 summary |
| 顺序执行 | asyncio.gather 并行, 时间 ≈ max() 不是 sum() |
| Scope creep | 每 subagent 一个 task, 单一职责 |
| 失败放大 | 一个 subagent 失败, 主 agent 拿到 status=failed 但其他 subagent 继续 |

## 主 agent ↔ subagent 协议

主 agent 调一个 `delegate_to_subagent` 工具 (跟普通 `read_file` 一样, 只是更复杂):

```json
{
  "subagent_type": "researcher",
  "task": "Search competitors for X. Return top 3 with pricing.",
  "tools_allowed": ["web_search", "read_file"]
}
```

Subagent 完成后, 返回**结构化 result**:

```json
{
  "status": "completed",     // 或 "failed", "partial"
  "summary": "Top 3 competitors: ...",
  "artifacts": {
    "web_search": ["..."],
    "read_file": ["..."]
  },
  "n_iterations": 4,
  "elapsed_ms": 1250.3
}
```

主 agent 只看 `summary`. `artifacts` 是 debug 用的, 可选传回.

## 跟 ReAct 的关系

主 agent 自己也是 ReAct loop (见 [01-simple](../01-simple)). `delegate_to_subagent` 只是它的一个工具, 跟 `read_file` 同级.

区别是这个工具的"工具体"是一个完整的 ReAct loop (子 agent), 返回时只给摘要:

```
   Main Agent ReAct loop:
     while not done:
       LLM(main_prompt + main_tools)
       → tool: delegate_to_subagent("researcher", "search X")
                  ↓
                  Sub Agent ReAct loop (isolated context):
                    while not done:
                      LLM(sub_prompt + sub_tools)
                      → tool: web_search(...)
                    return summary  ←← 主 agent 只见这一行
       ← summary
       继续主 agent loop
```

## 并行 vs 串行

```python
# 串行 (单 agent 干一切, 或单发 delegate):
r1 = await delegate("researcher", "task A")    # 等 10s
r2 = await delegate("researcher", "task B")    # 再等 10s
r3 = await delegate("researcher", "task C")    # 再等 10s
# 总时间 30s

# 并行 (delegate_parallel):
r1, r2, r3 = await asyncio.gather(
    delegate("researcher", "task A"),
    delegate("researcher", "task B"),
    delegate("researcher", "task C"),
)
# 总时间 ≈ 10s (max), 省 67%
```

并行的前提是 LLM client 是 **async** (httpx.AsyncClient 而不是 sync). 教学版用 mock LLM 简化, 但接口已经是 async 协程.

## 工具限制 (sandbox)

不同 subagent 能用的工具应该不同:

| Subagent type | 允许工具 | 禁止工具 |
|---------------|----------|----------|
| `researcher` | web_search, read_file | write_file, exec |
| `coder` | read_file, write_file, exec | web_search |
| `auditor` | read_file | 一切写入类 |

主 agent 调 `delegate(type, task, tools_allowed=[...])` 时传白名单, subagent 跑 ReAct loop 检查每次 tool_call 是否在白名单, 不在就返回 `[tool 'X' not allowed]`.

## 目录

```
.
├── python/
│   ├── orchestrator.py  # 🟢 SubAgent + Orchestrator + SubAgentResult
│   ├── main.py          # 3 个 researcher 并行调研 RoPE/RMSNorm/SwiGLU
│   ├── test.py          # 8 个测试: 基本运行 / 工具限制 / max_iter / 失败 / 路由 / 并行 / 隔离
│   └── requirements.txt
└── README.md
```

## 跑起来

```bash
cd python && pip install -r requirements.txt
cp .env.example .env  # 编辑填 API_KEY + MODEL_ID

python test.py    # 8/8 passed (mock LLM, 不调外网)
python main.py    # 真调 LLM, 3 个 subagent 串行 vs 并行对比
```

`main.py` 真 LLM 输出大致:
```
>>> 串行: 112026 ms (3 个 subagent 一个接一个)
>>> 并行: 139031 ms

>>> 加速比: 0.81×  ← 比串行还慢!

📋 Subagent #1 (RoPE):  status=completed, iter=2, ms=130114
   summary: **RoPE (Rotary Position Embedding)** is a positional encoding...

📋 Subagent #2 (RMSNorm):  status=completed, iter=2, ms=139031
   summary: ## RMSNorm Summary ... removes mean-subtraction step...

📋 Subagent #3 (SwiGLU):  status=completed, iter=2, ms=135659
   summary: ## Summary ... combines Swish with a gating mechanism...
```

### 实测发现: 加速比可能 < 1!

本地 MLX server 是**单 instance, 不支持真并发推理**: 3 个并发请求打过去, server 端排队 + lock 竞争, 比顺序处理还慢. 这跟 vLLM / TensorRT-LLM 的 continuous batching 完全不同.

什么时候 subagent 并行才真有加速:

| 场景 | 加速 | 原因 |
|------|------|------|
| 本地 MLX / Ollama (单 instance) | ≤ 1× | 服务端排队 |
| vLLM / SGLang 支持 batched inference | 接近 N× | 服务端真并行 |
| Claude / OpenAI / Gemini API | 接近 N× | 云端多副本 |
| 不同 subagent 调不同模型 | 接近 N× | 没资源竞争 |
| Subagent 主要时间在工具 (而不是 LLM) | 接近 N× | IO-bound, 并发友好 |

**结论**: subagent 并行架构本身是对的, 但**前提是 LLM 服务能并发承载**. 否则只是把 sequential overhead 转成 contention overhead.

## 常见坑

- ❌ **subagent 完整 messages 回传给主 agent** → context 污染没解决, 主 agent 又看到所有 tool 历史. 只回 summary
- ❌ **subagent 共享同一个 messages list** → 多 agent 并行写同一个 list, race condition. 每个 subagent 独立实例
- ❌ **同步 LLM client + asyncio.gather 不包 to_thread** → 没真并发 (sync 阻塞 event loop). 本实现用 `asyncio.to_thread()` 把 sync llm_call 丢 thread pool, IO-bound 时能并发
- ❌ **以为 asyncio.gather 就能加速** → 还得 LLM 服务端支持并发. 本地 MLX 单 instance 时, 并行可能比串行还慢 (见上文实测)
- ❌ **subagent 失败让主 agent 也死** → 主 agent 看 result.status, failed 也是合法状态, 继续后面的工作
- ❌ **工具白名单只在主 agent 检查** → subagent LLM 还是可能调禁止工具 (LLM 不读白名单); 必须在 subagent **执行** tool 时检查
- ⚠️ **subagent context 太干净反而失忆** → 任务描述要给足前因后果, subagent 看不到主 agent 之前的对话
- ⚠️ **subagent 之间想"互相协调"** → 不行, 它们没共享 state; 必须由主 agent 编排 (这是设计目的, 不是 bug)
- ⚠️ **并行数量太多 (e.g. 50)** → LLM API rate limit, 用 semaphore 限并发
- ⚠️ **subagent summary 太长** → 失去隔离意义; summary 应该是结构化 markdown, 几百 token 内

## 什么时候**不该**用 subagent

- 任务串行依赖 (B 用 A 的输出) → 单 agent 就行
- 任务很短 (≤ 3 步) → 启 subagent 的开销大于收益
- LLM 已经擅长该任务 → 没必要拆
- 需要跨 subagent 共享中间状态 → 设计错了, 应该回到单 agent

## 跟 Claude Code Task tool 的对照

Claude Code 内置的 [Task tool](https://docs.anthropic.com/claude-code/sub-agents) 就是这个模式的生产实现:

| Claude Code | 教学版 |
|-------------|--------|
| `subagent_type` 参数 (general-purpose, etc.) | `agent_type` 字符串 |
| Task tool 返回单条消息 | `SubAgentResult` dataclass |
| 内置 isolation: "worktree" 用 git worktree 隔离文件改动 | 不实现 (只隔 messages) |
| Background mode (run_in_background) | 不实现 |
| 主 Claude 自动选 subagent_type | 主 LLM 显式指定 |
| Tools 子集自动按 agent_type 推断 | 主 agent 显式传 tools_allowed |

核心模式 (isolation + delegate + aggregate) 1:1 一致.
