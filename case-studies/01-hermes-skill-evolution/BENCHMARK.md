# 原版 vs 复刻 Demo —— 差距和往生产推的清单

复刻 demo 是"看清原理"用的，不是生产级。差距列下，每项是一个**单独可拆的工程子任务**，按价值排了序。

## 功能差距矩阵

| 维度 | hermes 原版 | 本 demo | 差距代价 |
|------|------------|---------|---------|
| **后台执行** | 真线程 (`run_agent.py:15672`)，不阻塞主对话 | 同步跑 | 用户感知到 LLM 调用多一倍延迟 |
| **触发器** | tool_call ≥ 10（可配） | 每轮都跑 | 简单对话浪费一次 LLM 调用 |
| **skill 装载** | 索引模式 + 按需 `skill_view` | 索引 + 全文都塞 | skill 多了 system prompt 撑爆 |
| **缓存** | LRU + mtime snapshot 两层 | 每次扫盘 | skill 多了启动慢 |
| **skill 结构** | SKILL.md + references/ + templates/ + scripts/ | 单 SKILL.md | 没法存细节附件 / 可执行脚本 |
| **frontmatter** | 完整 YAML（name, description, platform, when_to_use, ...） | description 一个字段 | skill 召回精度差 |
| **action 类型** | create / edit / patch / write_file | 只有 save (overwrite) | 没法精准改一行 |
| **反例清单** | 完整版 (`run_agent.py:4147-4166`)，几十条 | 缩略 4 条 | 容易把环境问题误记成 skill |
| **冲突解决** | umbrella + 合并提示 | 同名直接覆盖 | 同主题 skill 会互相覆盖 |
| **多用户 / namespace** | 单用户 | 单用户 | 不能多租户 |

## 复现一次的最小投入

| 顺序 | 任务 | 投入 | 价值 |
|------|------|------|------|
| 1 | reviewer 调用改成 `threading.Thread`，主对话不等它 | 5 行 | 高（用户体感差异大） |
| 2 | 触发器从"每轮"改成 "tool_call ≥ N" | 10 行 | 中（demo 没有真工具调用，可改成"user message ≥ N"） |
| 3 | skill 装载改成索引模式 + 提供 `skill_view` 工具 | ~50 行 | 高（决定能不能 scale 到几十个 skill） |
| 4 | mtime 缓存：扫盘前 stat 一遍，跟 snapshot 比 | ~30 行 | 中（skill < 20 个时无所谓） |
| 5 | action=edit/patch 精确改：用 diff 或行号 | ~80 行 | 中（避免 overwrite 丢内容） |
| 6 | 反例清单写全，配 fixture 测试（环境错误 → skip）| 1 天 | 高（决定 skill 库会不会变垃圾堆） |

我推荐先做 1 + 3 + 6。其它优先级低很多。

## 容易踩的坑（我跑 demo 时遇到的）

1. **小模型不肯输出纯 JSON** —— 7B 以下的模型经常会在 JSON 前后加解释。`reviewer.py` 的 `_extract_json` 容错就是为这个。生产级还要加 retry。
2. **skill 越积越多，system prompt 爆** —— 这是切到索引模式的**真实**触发点，不是"未来再说"，5 个 skill 就开始难受。
3. **同义 skill 互相覆盖** —— 模型一会儿叫 `code-style-preference`，一会儿叫 `coding-conventions`。hermes 在 prompt 里反复强调 "umbrella skill" 就是治这个。复刻 demo 暂时无解，因为没实现 list + view 工具，reviewer 不知道库里已经有啥。**修这个就是优先级 3 的工作**。
4. **reviewer 把环境问题刻成 skill** —— 跑过几次发现 "API timed out, must use shorter prompts" 被记成 skill。这种 "negative claim" 一旦写进 skill，几个月后还在影响行为。hermes 的反例清单不是装饰。

## 想往生产推到底要什么

复刻 demo 离生产还差一道大墙。生产化拆开是这些模块（按依赖顺序）：

1. **持久化层**：文件锁、原子写、目录结构、备份。skill 是用户资产，丢了不能恢复。
2. **召回层**：当前 demo 全塞模式撑不过 20 个 skill。生产要么按主题分桶 + topic 分类器，要么用 embedding 召回。
3. **质量层**：自动检测 skill 是否过期 / 是否被违反 / 是否互相冲突。hermes 用 "background curator"（`_COMBINED_REVIEW_PROMPT` 附近）做合并。
4. **审计层**：每次 skill 改动留 trace（谁改、为啥改、改之前长啥样）。强烈建议直接拿 git。
5. **回退层**：用户能 `/forget-skill foo` 临时禁用。hermes 在 `get_disabled_skill_names()` 处理。

每一层都是独立可做的 demo —— 也就是说本目录可以衍生出 `02-hermes-skill-namespacing`、`03-skill-retrieval-by-embedding`、`04-skill-conflict-detection`…… 想清楚再开新 case。
