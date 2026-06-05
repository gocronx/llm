# 01 · Skill Loader Demo

Anthropic Skills 的本地实现。把"指令 + 触发条件 + 正文"打包成 `SKILL.md`，按用户请求选相关 skill 注入 system，不相关的不占 context。代码就在 `python/`（334 行，`python test.py` 8/8 通过），下面的原理逐条对应到代码行号。

Claude Code 的 Skills、Codex 的 `$skill`、各家 agent 框架的"技能包"，剥掉营销外壳后是同一个东西：**一段写好的提示词，加上"什么时候该用它"的元信息，存成文件，按需注入对话**。

## 一、Skill 的本质：打包

没有 Skill 机制时，你想让模型擅长写 SQL、改简历、做代码安全审查，只能把所有这些指令一股脑塞进 system prompt。指令越攒越长，每次请求都全量携带。

Skill 做的事就一件：把每段领域指令**卷起来装盒、贴上标签、上架**。

![把长指令打包成带标签的盒子](assets/skill-principles-illustrations/01-pack-instructions.png)

落到文件上，一个 Skill 就是一个带 YAML frontmatter 的 markdown（见 `python/skills/sql-query-builder.md` 等 5 个真实样例）：

```markdown
---
name: sql-query-builder        # 标签：唯一名字
description: 把自然语言需求转成 SQL……   # 标签：一句话用途
triggers: [sql, 查询, select]   # 标签：触发词
---

你是 SQL 专家。规则：
1. 永远用参数化查询……          # 盒子里的正文
```

就这么多。没有代码、没有沙箱、没有魔法——**Skill 的"安装"就是把文件放进目录，"卸载"就是删文件**。完整形态的 Skill 还可以带参考资料和脚本，一张卡总览：

<p align="center"><img src="assets/skill-principles-illustrations/05-skill-anatomy.png" width="420" alt="长指令打包成技能（知识卡）"></p>

## 二、为什么要按需加载：context 是背包，不是仓库

把所有指令常驻 system 的问题不是"乱"，是**贵且互相干扰**：

1. **token 成本**：每次请求都为用不上的指令付费；
2. **注意力稀释**：模型遵循指令的能力随 system 长度下降，10 个领域的规则挤在一起，每个都执行得更差；
3. **指令打架**："回复要简短"（客服 skill）和"逐条详细分析"（审查 skill）同时在场，模型只能猜。

所以 Skill 机制的核心动作是**选择性注入**：每次请求只把相关的 1-2 个 skill 放进背包，其余留在架子上。

![背包有限，只带相关的盒子](assets/skill-principles-illustrations/02-limited-backpack.png)

对应代码里的组装函数（`python/router.py:93`）：

```python
def compose(skills, loaded):
    if not loaded:
        return Composed(BASE_SYSTEM, [])      # 没命中就是裸 system
    blocks = [BASE_SYSTEM, ""] + [s.as_system_block() for s in loaded]
    return Composed("\n\n".join(blocks), ...)  # 命中几个拼几个
```

## 三、两层结构：目录卡 vs 书库

要做到"先判断相关、再加载正文"，Skill 文件必须拆成两层，**便宜的一层用来索引，贵的一层用来执行**：

| 层 | 内容 | 多大 | 谁读 |
|---|------|------|------|
| frontmatter（目录卡）| name / description / triggers | 几十 token | 路由器：常驻或低成本扫描 |
| body（书）| 完整领域指令 | 几百到几千 token | 主模型：选中才注入 |

这就是 Anthropic 文档里说的 **progressive disclosure（渐进式披露）**：模型先看到一排目录卡，确认需要哪本书，才去库里取。

![先翻目录卡，再取地下库的书](assets/skill-principles-illustrations/03-card-vs-book.png)

解析就是一个正则切两半（`python/loader.py:15`）：

```python
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)

# group(1) → yaml.safe_load → 目录卡（name/description/triggers）
# group(2) → 原样保留      → 书（body）
```

工程上唯一值得加的优化是按 mtime 缓存（`loader.py:52` 的 `load_skills_cached`）：文件没改就走内存，改了自动失效——skill 热更新不用重启进程。

## 四、加载时机：三种路由，三档成本

"哪个 skill 相关"是 Skill 机制里唯一有分歧的设计点。`python/router.py` 实现了全部三种，对照着读最清楚：

![三条通道：关键词闸机、小模型代选、自己取](assets/skill-principles-illustrations/04-three-routes.png)

| 策略 | 怎么选 | 额外 LLM 调用 | 适合 |
|---|---|---|---|
| `route_keyword` | triggers 全词命中计 1 分，description 词命中计 0.3 分，排序取 top-k | **0** | 触发词可枚举的领域（SQL、翻译） |
| `route_llm` | 把目录卡列表丢给一个小模型，只让它输出 JSON 数组 | **+1 次小调用** | 用户表述发散、关键词举不全 |
| `route_implicit` | 把目录卡放进 system，注册一个 `skill_view(name)` 工具，主模型自己决定调不调 | **嵌在主对话里** | 最贴近 Claude Code / Codex 的真实形态 |

三种没有优劣，是成本和召回的滑杆：关键词闸机免费但死板；小模型代选准一点、贵一次调用；自己取最聪明，但要求主模型可靠地使用工具（所以 `run_implicit` 里必须有 `max_iters=3` 兜底，见 `router.py:128`——否则模型可能反复 `skill_view` 不收手）。

`route_llm` 还有个实战细节值得记：**别让路由模型输出"理由"**。它一解释就开始漂移，所以 system 里写死"只输出 JSON 数组"（`router.py:40`），再配一个从废话里抠数组的 `_extract_array` 兜底。

## 五、共通的坑

四个坑全部在 `test.py` 里有断言覆盖：

- ❌ **body 太长** —— 多加载两个就把 context 吃光，违背了机制的初衷。一个 skill 干一件事，长了就拆。
- ❌ **triggers 只写一种语言** —— 用户说"查询"而 trigger 只有 "sql"，keyword 路由直接漏。中英同义词都铺上。
- ❌ **implicit 模式不设迭代上限** —— 主模型可能循环加载，`max_iters` 是必须的护栏。
- ❌ **让路由 LLM 说理由** —— 越解释越偏，只许输出名字数组。

## 六、跑起来验证

```bash
cd python
pip install -r requirements.txt
python test.py    # 8/8：解析、缓存失效、三种路由、组装
python main.py    # 同一个问题在三种策略下的对照输出
```

看完代码再回头看各家产品就会发现：Claude Code 的 SKILL.md、Codex 的 skills 目录、各框架的 plugin manifest，差异只在目录卡的字段名和路由策略的选型——**"打包 → 索引 → 按需注入"这三步，是所有 Skill 机制共享的骨架**。
