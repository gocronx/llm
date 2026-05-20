# 22 · LLM-Driven Summary Compression

> 已经看了 [21](../21-context-governance)? 这里讲怎么用 LLM 自己**总结**老 history (而不是规则式截断).

抽自 hermes-agent `agent/context_compressor.py:793-891`. 类似 Claude Code 的 `/compact`. 适合长会话 (50+ 轮) 的 context checkpoint.

## 跟 21 的关系

21 教**规则式**治理 (代码砍/截/替占位符), 22 教**模型式**总结 (LLM 自己消化).

| | 21 microcompact | 22 LLM summary |
|--|-----------------|-----------------|
| 谁干活 | 规则代码 | LLM (额外 1 次 forward) |
| 操作单位 | 单条 tool result | 多轮 (user+assistant+tools) |
| 输出 | `[result omitted]` 占位 | 结构化 markdown 摘要 |
| 信息损失 | 完全丢工具结果 | LLM 保留关键 (理论上) |
| 成本 | 0 | 1 次 LLM forward (~5-10 秒) |
| 适用场景 | 中等会话 (5-20 轮) | 长会话 (50+ 轮) 一次性 checkpoint |

**实战栈**: 先 21 规则压缩兜底, 21 还顶不住时 22 LLM 总结. 两者叠加.

## 压缩逻辑

```
   原 messages:
   [system]
   [user: "Task: refactor auth"]    ← first_user (任务定义, 保住)
   [assistant + tool_calls]         ┐
   [tool: ...]                      │
   [assistant + tool_calls]         │  middle: 要被 LLM 总结的区域
   [tool: ...]                      │
   ...                              │
   [assistant + tool_calls]         │
   [tool: ...]                      ┘
   [assistant: "I'll continue..."]   ┐
   [user: "ok"]                     │  recent: 保留原文 (keep_recent_turns)
   [assistant: "Now do X"]          │
   [user: "Q?"]                     ┘

   压缩后:
   [system]
   [user: "Task: refactor auth"]                                ← 不动
   [system: "[Conversation summary, 18 prior msgs] ## Active Task ..."] ← 新增
   [assistant: "I'll continue..."]                              ┐
   [user: "ok"]                                                 │ 不动
   [assistant: "Now do X"]                                      │
   [user: "Q?"]                                                 ┘
```

减少: 18 → 7 条 (~ 70% 压缩率, summary 约占 middle 的 5-15% token).

## 结构化模板

不让 LLM "随便总结", 而是给一个固定模板. 这样 summary 既能被机器解析, 也能被人读. 教学版 7 个字段:

| 字段 | 内容 |
|------|------|
| **Active Task** | 用户最新指令 (复制原话, 最重要字段) |
| **Goal** | 用户整体目标 |
| **Completed Actions** | 已做的: N. ACTION target — outcome [tool: name] |
| **In Progress** | 当前正在做什么 |
| **Blocked** | 错误 / 卡住的地方 |
| **Key Decisions** | 已定的技术选择 + WHY |
| **Pending User Asks** | 用户问过但没答的 |
| **Remaining Work** | 还要做什么 |

hermes-agent 原版用 12 个 section, 教学版砍到 7 个核心 (省 prompt 长度 + 教学清楚).

## 关键工程细节

### 1. 失败 fallback + cooldown

LLM 总结可能失败:
- Rate limit (HTTP 429)
- 上下文超限 (要总结的 middle 本身已超 LLM context)
- LLM 返回空字符串 (有时会发生)

失败后**立刻退到 cooldown 模式** (60s 内不重试). 否则一个会话里反复重试浪费 token 还可能死循环.

教学版用 `time.monotonic()` 实现, 真生产用 redis/db 跨进程持久化 cooldown.

### 2. focus_topic (Claude Code `/compact` 风格)

长会话里有时只关心一个子任务. 比如对话 100 轮, 最近 30 轮全是 `refactor auth`, 你想 `/compact refactor auth`, 让总结**只**保留这个话题的细节, 其余高度压缩.

教学版把 `focus_topic` 字符串注入 prompt, 让 LLM 自己取舍.

### 3. Summary 目标长度

太短 (e.g. 100 token): LLM 总结不全, 关键信息丢
太长 (e.g. 3000 token): 没压缩多少, 还多花了 LLM forward 钱

经验值: 总结后 token 数 ≈ 被压缩区的 **5-15%**. 对应 `target_summary_tokens` 配置.

### 4. 增量更新 (iterative update)

已有 summary 时 (上一轮已经 compact 过), 不要重新总结全部, 而是在 summary 基础上 append 新进展. 省 prompt token, 也避免反复转译丢失.

教学版没实现这步 (留作扩展); hermes 原版 line 891+ 有 iterative path.

## 目录

```
.
├── python/
│   ├── compressor.py    # 🟢 LLMCompactor + CompactConfig + CompactResult
│   ├── main.py          # 真调 LLM, 压缩一段"refactor auth"对话
│   ├── test.py          # 8 个测试: 切片 / fallback / cooldown / focus_topic
│   └── requirements.txt
├── .env.example
└── README.md
```

## 跑起来

```bash
cd python && pip install -r requirements.txt
python test.py    # 8/8 passed, 不调外网 (mock LLM)
python main.py    # 真调 LLM API, 输出 summary markdown
```

`main.py` 输出大致:
```
>>> 原始 history: 19 条消息
   估算 tokens: 1248
   should_compact: True (阈值 1000)

>>> 调用 LLM 压缩中...
>>> 压缩成功. 总结了 14 条 middle messages
   新 messages 数: 8
   新估算 tokens: 380   ← 压缩了 ~70%

>>> LLM 生成的 summary:
------------------------------------------------------------
## Active Task
[看起来 done 了, 帮我总结一下做了什么]

## Goal
将 auth 模块从 session-based 迁移到 JWT

## Completed Actions
1. READ auth/middleware.py — 200 行 session 中间件 [tool: read_file]
2. READ models/user.py — User class, 无 JWT 字段 [tool: read_file]
3. WRITE auth/jwt.py — 64 行 sign_token + verify_token [tool: write_file]
4. PATCH auth/middleware.py — 改 verify_token [tool: write_file]
5. TEST tests/auth — 3/12 fail (exp/invalid/refresh) [tool: run_tests]
6. PATCH auth/jwt.py — 加 exp=now+24h [tool: write_file]
7. TEST tests/auth — 12/12 passed [tool: run_tests]
...
```

## 常见坑

- ❌ **LLM 总结时不给结构化模板** → LLM 自由发挥, 输出"我帮你做了几件事..."这种废话, 信息密度低
- ❌ **summary 直接当 user 消息插入** → 模型会以为是用户说的话; 当 system message 插入是对的
- ❌ **失败后立刻重试** → rate limit 场景下会越打越频繁, 必须 cooldown
- ❌ **不保 first_user (任务定义)** → 总结的 LLM 看不到原始任务, 摘要会偏题
- ❌ **不保最近 N 轮** → LLM 失去最近上下文, 答非所问
- ❌ **prompt 里 messages 序列化没截单条 content** → 一条 tool result 50KB 直接撑爆 summarizer 的 context window
- ⚠️ **summary 跟用户语言不一致** → preamble 里要求 "same language as conversation", 否则中文对话被总结成英文
- ⚠️ **API key / secrets 在 history 里** → preamble 必须有 "REDACTED any credentials" 指令, 否则会写到 summary 里被持久化
- ⚠️ **summary 的"## Active Task"字段不准** → 这是最重要字段; 让 LLM "verbatim copy" 用户原话, 别让它意译
- ⚠️ **iterative update 没实现** → 长会话第二次 compact 时不该从零开始, 该 incremental

## 跟 hermes-agent 原版的对照

| hermes 原版 | 教学版 |
|------------|--------|
| 12 个 section 模板 | 7 个核心 section |
| iterative update (基于上次 summary) | 不实现 |
| `summary_model` 可指定单独的小模型 | 复用主 LLM |
| `_compute_summary_budget` 动态算 budget | 固定 `target_summary_tokens` |
| `_prune_old_tool_results` 配合 H21 风格的预压缩 | 不实现 |
| Azure / OpenAI content filter 友好的措辞 | 跟原版一致的 preamble |
| `_fallback_to_main_for_compression` 多级 fallback | 单级: 失败 → cooldown |
| token estimator 用 tiktoken | chars/4 toy estimator |

核心算法 (模板 + 切片 + cooldown) 1:1 保留, 砍掉的是 hermes 特有的 multi-model / multi-fallback 设施.
