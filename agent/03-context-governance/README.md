# 03 · Context Governance

> 不熟 ReAct 范式? 先看 [01-simple](../01-simple) 的 "什么是 ReAct" 一节.

[01-simple](../01-simple) 教了 ReAct 长啥样 —— 一个 71 行的 while 循环, 在玩具任务上跑 5 轮没问题. 但真把它塞到 production 里, 跑到 20+ 轮就开始死. 死的不是逻辑, 是 **context 形态**: API 返回 400, 或 LLM 因超 context window 拒绝.

本 demo 抽自 nanobot `runner.py:1103-1283` 的 5 步治理组合拳, 让 ReAct 撑到 50+ 轮不崩. 简化成 self-contained 教学版 (无外部 session/storage 依赖).

![小黑只誊抄一张精简副本去喂模型，身后锁链拴住的原账本一字不动](assets/03-governance-illustrations/01-view-not-memory.webp)

## 为什么会崩 —— 三个具体场景

### 场景 1: 结构崩 (API 400)

LLM 第 17 轮调了 `web_fetch`, 历史变这样:

```jsonc
[
  {"role": "user", "content": "..."},
  // ...前 16 轮 (assistant + tool)...
  {"role": "assistant", "tool_calls": [{"id": "c17", "function": {"name": "web_fetch", ...}}]},
  {"role": "tool", "tool_call_id": "c17", "content": "..."}
]
```

第 18 轮你 (或某个外部 pruner) 决定砍掉前 10 轮历史. 砍完:

```jsonc
[
  {"role": "user", "content": "..."},
  // 砍掉了 assistant.tool_calls 那条, 但 tool 留下了 ↓
  {"role": "tool", "tool_call_id": "c7", "content": "..."},   // ← 孤儿! 没有对应的 assistant
  // ...
]
```

OpenAI/Anthropic API 收到这个 messages 直接 **400**: *"tool message must be preceded by assistant message with matching tool_calls"*. 整轮发不出去.

### 场景 2: 体积崩 (单条爆)

`web_fetch("https://wikipedia.org/...")` 返回 50KB 文本. 这一条 tool message 就吃 12k token. 还没等总量超 context, 单条就把当轮请求撑爆 —— provider 报 `input too long`.

### 场景 3: 预算崩 (累计爆)

20 轮 `search_products`, 每条 result 4KB. 累计 ~80KB ≈ 20k token, 超 8k context window. LLM 拒绝.

---

## 五步治理 —— 每步给微型例子

每个函数都是**纯函数** (不改入参), 接收 `messages: list[dict]` 返回新的 `list[dict]`.

### 1. `drop_orphan_tool_results` —— tool 没爹 → 删

扫一遍 messages, 收集所有 `assistant.tool_calls[*].id` 到一个 declared 集合. 然后遍历 tool 消息, `tool_call_id` 不在 declared 里的就是孤儿, 丢掉.

```jsonc
// 输入: ORPHAN 没爹 (前面没有 assistant.tool_calls 宣告过 id=ORPHAN)
[
  {"role": "user", "content": "hi"},
  {"role": "tool", "tool_call_id": "ORPHAN", "content": "..."},   // ← 删
  {"role": "assistant", "tool_calls": [{"id": "c1", ...}]},
  {"role": "tool", "tool_call_id": "c1", "content": "..."}
]
// 输出: 3 条 (移除 ORPHAN)
```

### 2. `backfill_missing_tool_results` —— tool_call 没儿 → 补占位

跟 #1 对偶. assistant 宣告了 `tool_calls[*].id` 但找不到对应 tool message, 补一条 `"[Tool result unavailable]"` 占位. **不能删 assistant**, 删了 LLM 会失忆.

```jsonc
// 输入: assistant 宣告了 c1, 但没 tool 跟随
[
  {"role": "assistant", "tool_calls": [{"id": "c1", ...}]},
  {"role": "user", "content": "继续"}    // ← 跳过了 c1 的 tool
]
// 输出: 中间插一条占位
[
  {"role": "assistant", "tool_calls": [{"id": "c1", ...}]},
  {"role": "tool", "tool_call_id": "c1", "content": "[Tool result unavailable — call was interrupted or lost]"},
  {"role": "user", "content": "继续"}
]
```

### 3. `microcompact` —— 老 tool result → 一行摘要

只动**只读类**工具的旧结果 (read_file / web_fetch / grep / search 等, 在 `COMPACTABLE_TOOLS` 里). 保留最近 N 个 (默认 N=10) 的原文, 更老的替成 `[<tool_name> result omitted from context]`.

跟 snip 的区别: snip 是"砍掉整条", microcompact 是"留壳去肉" —— LLM 还能看到这步**发生过**, 但不再吃大块 token.

```jsonc
// 输入: 15 个 web_fetch 的 tool, 每个 6KB
// 输出 (keep_recent=10): 前 5 个被压成 "[web_fetch result omitted from context]" (~36 chars)
//                       后 10 个保完整原文
```

**为什么只压只读类工具**: `write_file` / `exec` 这种**有副作用**的工具压了就麻烦 —— LLM 看不到副作用历史会重复执行 (e.g. 再写一遍同名文件). 别加进 `COMPACTABLE_TOOLS`.

### 4. `apply_tool_result_budget` —— 单条太大 → 截

单条 tool result 超过 `max_tool_result_chars` 就截断, 末尾标 `…[N chars truncated]`.

```jsonc
// 输入: tool content 长度 20000 字符
// 输出 (max=4000): content 截到 3800 字符 + "\n…[16200 chars truncated]"
```

跟 microcompact 的区别: budget 是**对所有 tool message** 限单条大小, microcompact 是**只对旧的只读工具**做整条替换. 两者协作: budget 控单点, microcompact 控历史累积.

### 5. `snip_history` —— 总 token 超预算 → 保任务 + 末尾单元

最复杂的一步, 也是 09 ReAct 长跑的核心防线. 算法:

1. 预算 = `context_window_tokens - reserve_for_output - safety_buffer`
2. 若总 token ≤ 预算, 直接返回 (不动)
3. 否则: 保 `system` 消息 + **第一条 user (任务定义)** + 反向收集 **末尾若干 (assistant + 它的 tool*) 单元**

**为什么按 unit 整体保/丢**: 砍到一半的 `(assistant.tool_calls, tool, tool)` 三元组会留孤儿. 即便末尾 drop_orphan 兜底, "半截 unit" 也会被全清掉, 还不如一开始就按 unit 保.

**为什么第一条 user 必保**: 任务定义丢了 LLM 会偏题. 哪怕预算不够也保, 上层 (provider 自己的 truncation) 会再修.

```jsonc
// 输入 (4000 token context, 1024 reserve_for_output, 1024 safety_buffer = 1952 实际预算):
//   system + user_task + (asst, tool)×6, 每个 tool result 1500 token = 总 ~9000 token
//
// 输出: system + user_task + (asst, tool)×1   ← 末尾只保 1 个完整单元就到预算了
```

---

## 核心约束 —— "View 喂模型, 不动真实记忆"

```python
view = govern(self.messages, ...)              # ← 治理生成新 list
resp = client.chat.completions.create(view)    # ← 喂治理后的 view 给模型
# self.messages 完全不变, 下一轮还是从原始 self.messages 跑 govern()
```

**为什么这样设计**:
- `microcompact` / `apply_tool_result_budget` 是**有损**变换 (替成短摘要 / 截断). 直接改 self.messages 会把这些"假占位"回灌进真实历史, 跑 30 轮下来记忆里全是占位符, LLM 失忆.
- 同理 `backfill_missing` 补的 `[Tool result unavailable]` 占位字符串, 不该污染真实历史
- 治理是"我现在要喂模型, 临时整理一下" —— 像是数据库的 view, 不是 update.

## govern() 入口的顺序

```
              ┌──────────────────────────────────────────────────┐
              │  每轮 LLM 调用前: view = govern(messages, ...)    │
              ├──────────────────────────────────────────────────┤
              │  1. drop_orphan_tool_results       清结构        │
              │  2. backfill_missing_tool_results  补结构        │
              │  3. microcompact                   压老果        │
              │  4. apply_tool_result_budget       剪长果        │
              │  5. snip_history                   兜总量        │
              │  6. drop_orphan + backfill         snip 后再修结构│
              └──────────────────────────────────────────────────┘
```

**为什么是这个顺序**:
- **先结构再体积**: drop+backfill 是 0 损耗的修复, 先做掉避免后续步骤在"坏结构"上操作
- **先 microcompact 再 budget**: 老的 5KB tool result 直接被 microcompact 替成 36 chars, 就不用 budget 截到 4KB 了 (省一次拷贝)
- **snip 最后**: snip 是按 token 总量做决策的, 必须等前面把单条都压完再算账
- **末尾再来一次 drop+backfill**: snip 砍可能产生新孤儿 (理论上不会, 因为按 unit 砍; 但留着双保险)

---

## 参数调优

三个旋钮:

| 参数 | 默认 | 调小风险 | 调大风险 |
|------|------|---------|---------|
| `context_window_tokens` | 跟模型一致 (e.g. 8000) | snip 砍太狠, LLM 失忆 | 实际超 provider 限制, 直接 400 |
| `max_tool_result_chars` | 8000 (~2k token) | 单 tool result 信息损失 | microcompact + snip 顶上来; 但单轮可能仍超 |
| `microcompact_keep_recent` | 10 | ≤ 2 时 LLM 失去最近上下文, 答非所问 | 旧 result 占位太久, snip 会更频繁触发 |

**实战经验**:
- 7B 量级小模型 (Qwen2.5-7B / Llama-3-8B): `context_window=4000`, `max_tool_result=2000`, `keep_recent=5`
- 70B+ 大模型 (Claude / GPT-4): `context_window=32000`, `max_tool_result=8000`, `keep_recent=15`
- 工具返回特别大 (文件读取 / 网页抓取): 把 `max_tool_result_chars` 调到工具单次返回的 P95

## 目录

```
.
├── python/
│   ├── governance.py   # 🟢 5 步函数 + govern() 入口 (243 行, 全是纯函数)
│   ├── agent.py        # 🟢 09 的 Agent + 每轮 govern() 钩子
│   ├── tools.py        # 复用 09 + web_fetch (返回 8KB, 触发治理)
│   ├── main.py         # 长对话演示, 真调 API
│   ├── test.py         # 7 个单测 (含 govern pipeline 集成)
│   └── requirements.txt
├── .env.example
└── README.md
```

## 跑起来

```bash
cd python
pip install -r requirements.txt

python test.py    # 7/7 passed, 不调外网
python main.py    # 真调 LLM API (需 .env), 会打 [govern] real=X → view=Y, X→Y tok
```

`test.py` 输出大致长这样:
```
✓ drop_orphan (kept 3/4)
✓ backfill_missing (len 3 -> 4)
✓ microcompact (3/5 compacted)
✓ microcompact skips small (0/15 should be 0)
✓ apply_budget (20000 -> 3825)
✓ snip_history (61msgs/7563tok -> 26msgs/3153tok)
✓ govern pipeline (orphan=False, pairs_ok=True, oversize=False, in_budget=True)
7/7 passed
```

`main.py` 真调 API 时 (本地 MLX server, Qwen 系列), 关键观察:
```
[tool] web_fetch(...) -> 5758 chars
[tool] web_fetch(...) -> 5758 chars
[tool] web_fetch(...) -> 5758 chars
[tool] search_products(...) -> 2390 chars
[tool] search_products(...) -> 2896 chars
[tool] get_weather(...) -> 51 chars
[govern] 9msgs, 5782->1799tok      ← 治理在最后一轮触发, token 压了 69%
```

## 实测数据

| 测试 | 输入 | 输出 | 效果 |
|------|------|------|------|
| `test_drop_orphan` | 4 条含孤儿 | 3 条 | 干净 |
| `test_apply_budget` | 1 条 20000 字符 | 1 条 3825 字符 | 截至预算 |
| `test_snip_history` | 61 条 / 7563 tok | 26 条 / 3153 tok | 砍 ~58% token |
| `test_govern_pipeline` | 32 条含孤儿+大果+超预算 | 全结构修复, 总量 ≤ 7952 tok | 5 步协作 |
| Mock 6 轮 + 收尾 | real=14 / 8451 tok | view=10 / 1835 tok | snip 触发 |
| **真 MLX 模型 6 工具** | **5782 tok** | **1799 tok** | **压 69%** |

## 常见坑

- ❌ **govern() 改了 self.messages** → 治理是"喂模型视角"不是"记忆", 改原状会把假占位/截断回灌进下一轮真实历史, 跑 30 轮全是占位符
- ❌ **snip 后不补 drop_orphan + backfill** → 即使按 unit 砍, 边界情况 (e.g. 第一条 user 后紧跟 tool message 但 assistant 在更早被砍) 仍可能漏孤儿; 末尾双保险
- ❌ **microcompact_keep_recent ≤ 2** → LLM 失去最近 N 轮工具结果, 答非所问 (e.g. "你说的"是什么"?")
- ❌ **chars/4 token 估算用于关键决策** → 中文密集 / 代码片段场景偏低 30-50%, 生产换 tiktoken (`encoding_for_model`) 或 Anthropic count_tokens API
- ❌ **microcompact 把带副作用的工具也压了** → `COMPACTABLE_TOOLS` 只放只读类; 别加 `write_file` / `exec` / `send_email`, LLM 看不到副作用会重复执行
- ⚠️ **provider 特化拒绝** → GLM 拒绝 `system→assistant` 序列, snip 把第一条 user 永远保住兜底; 其他 provider 类似的规则要在 snip 里加分支
- ⚠️ **snip 单条 tool 巨大** → 单个 tool result > 预算时 snip 砍不掉 (它按 unit 砍 unit 还是巨大); 必须先 budget 截到合理大小再 snip. govern() 顺序已保证这一点
- ⚠️ **govern() 在并发 agent 下共享 messages** → 多线程访问同一个 messages list 时, govern() 期间另一个线程往里 append, 行为未定义. 用 lock 包裹或者 copy 整个 list 后再 govern

## 什么时候**不用**这套治理

- **短任务 (≤ 5 轮)**: 09 的 71 行裸 ReAct 就够了, 加治理是过度工程
- **provider 自带 truncation** (e.g. Anthropic 的 `prompt_caching` + `auto_truncate`): 让 provider 替你做, 不重复造轮子
- **结构化 workflow** (e.g. LangGraph 的 state machine): 状态是 graph node 不是 messages, 治理无的放矢

什么时候**必须**用:
- ReAct 跑 10+ 轮以上
- 工具返回 unbounded 大小 (web/file/exec)
- 模型 context 比工具吞吐量小 (e.g. 7B 模型 4k context 配文件读取工具)

---

## 跟 nanobot 原版的对照

教学版**保留**的精髓:
- 5 步治理的算法本身 (1:1 对应, 简化了实现)
- "View 不污染真实记忆" 的核心约束
- govern() 调用顺序

**砍掉**的生产特性 (跟教学无关):
| nanobot 原版 | 教学版做法 |
|-------------|----------|
| `_normalize_tool_result` 走 session/storage 反查大对象 | 直接截断字符串 |
| `find_legal_message_start` 的 provider 规则集 | snip 里硬编码 "保第一条 user" |
| `estimate_prompt_tokens_chain` 用 tiktoken / Anthropic API | `chars/4` toy 估算 |
| `injection_callback` / `_MAX_INJECTIONS_PER_TURN` 系统提示注入 | 不实现 |
| `_partition_tool_batches` 并发工具批次 | 串行执行 |
| `_apply_tool_result_budget` 走 session resolver | 单参数 `max_tool_result_chars` |
| length_recovery / workspace_violation_counts | 不实现 |

剩下的是 **5 个治理函数本身**, 都是纯函数, ~243 行 governance.py, 可以从这个目录抽出来直接塞进任何 ReAct 框架.
