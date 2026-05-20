# 14 · Skill Loader — Anthropic Skills 风格的按需加载

**skills/*.md 是一堆带 YAML frontmatter 的小文件。用户来一个问题，**
**只把相关的 skill 注入到 system message，不相关的不占 context。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `loader.py` | 🟢 套出去用 | 发现 + 解析 SKILL.md，按 mtime 缓存 |
| `router.py` | 🟢 套出去用 | `route_keyword` / `route_llm` / `run_implicit` + `compose` |
| `main.py` | demo only | 三种路由策略对照 |
| `test.py` | demo only | 8 个纯逻辑测试 |
| `skills/` | demo 数据 | 5 个示例 skill |

## SKILL.md 格式

```markdown
---
name: sql-query-builder
description: 帮用户写 SQL 查询，覆盖 schema 设计、索引、性能调优
triggers:
  - SQL
  - 查询
  - 索引
---

# Body（被注入到 system 的内容）

写 SQL 时严格：...
```

## 三种路由策略

| 策略 | 怎么选 | LLM 调用 | 用在 |
|---|---|---|---|
| `route_keyword` | trigger 关键词命中 + description 词命中 | 0 | 低成本场景、确定性高的命中 |
| `route_llm` | 用一个小 LLM 调用挑名字 | +1 | 自然语言模糊匹配 |
| `run_implicit` | 主 LLM 通过 `skill_view` tool 自己加载 | 嵌入主对话 | Anthropic Skills 风格的"按需" |

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py     # 8/8 passed
python main.py     # 三种策略 vs 4 个问题
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| skill 用 markdown + YAML frontmatter | 人类可读、可 PR review、Anthropic Skills 用这个格式 |
| 缓存按 mtime 失效 | 编辑 skill 后下次自动加载，不要重启进程 |
| `route_llm` 路由用独立小调用 | 主调用看不到所有 skill 内容（省 context），路由器只看 description |
| `route_implicit` 把 skill_view 暴露给主 LLM | 让主 LLM 决定是否真要加载；description 看了不动手就不花钱 |
| `_extract_array` 容错抽 JSON | 即使模型瞎写一堆解释，最后一个 `[...]` 还能用 |

## 三种策略怎么选

- **静态规则能搞定** → keyword（最便宜）
- **触发词命中率低** → llm（多一次小调用，准很多）
- **skill 多到几十上百** → implicit（让主 LLM 自己挑，避免 router prompt 爆炸）

## 常见坑

- ❌ **skill body 太长** —— 多加载几个 skill 就爆 context；body 控制在 500 字内
- ❌ **trigger 列表只有同义词** —— 用户说"帮我翻译"匹配不上 `["translate"]`；多语言场景双语 trigger
- ❌ **implicit 模式忘了 max_iters** —— 主 LLM 可能反复 `skill_view`，要兜底
- ❌ **route_llm 不要让它输出"理由"** —— 字越多越容易漂；只让它出 JSON 数组
- ⚠️ **小模型对 implicit 模式不友好** —— 容易 mention skill name 而不真 call tool；用 keyword + llm 兜底
