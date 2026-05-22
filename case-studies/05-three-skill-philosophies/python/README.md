# Demo —— 三种 Skill 哲学 同台对照

约 600 行 Python 在**同一个 `SkillRegistry` 抽象**下跑出三种完全不同的"skill 获取"行为：

- `AutoEvolveRegistry` (hermes 风格) —— 后台 LLM 看 transcript 写 markdown
- `ForageRegistry` (zeroclaw 风格) —— 扫 catalog 评分自动装高分的
- `CuratedRegistry` (ironclaw 风格) —— 只允许装签名过且能力清单合规的

这是 case 03 多后端模式（`SandboxService` 三后端切换）的**架构层延伸**：从基础设施抽象到产品设计抽象。

## 跑法

```bash
cp ../.env.example .env  # 在 case 根目录, 填 API_KEY
pip install -r requirements.txt
python main.py            # 跑全 4 个场景
python main.py --scenario 1   # 单跑一个
python main.py --cleanup  # 清 .skills/
```

只有场景 1 和 4 需要调 LLM (AutoEvolve 走真 LLM)。其他场景纯本地, 秒出。

## 4 个场景

| # | 演示 | 涉及 LLM | 核心论点 |
|---|------|---------|---------|
| 1 | 三种 registry 看同样 transcript, 各自 acquire 产出 | ✅ | 同一抽象下三种哲学产出长得不一样 |
| 2 | forage 阈值过滤效果 + 调低阈值的脆弱性 | ❌ | 评分模型是采集模式的命门 |
| 3 | curated 拒装的 4 种情况 (无签名 / 不存在 / 能力越权) | ❌ | 策展靠多层校验, 不靠 LLM |
| 4 | 同样 hint, 三种 registry 各自生成的 system prompt 对比 | ✅ | skill 拼进 prompt 的尺寸 / 标签差异 |

## 文件分工

| 文件 | 角色 | 对应真实项目 |
|------|------|-------------|
| [skills.py](skills.py) | `Skill` 数据类 + `SkillRegistry` ABC + frontmatter 解析 | 三者共用的 SKILL.md 概念 |
| [backends/auto_evolve.py](backends/auto_evolve.py) | hermes 模式实现 | `run_agent.py:4077` _SKILL_REVIEW_PROMPT |
| [backends/forage.py](backends/forage.py) | zeroclaw 模式实现 | `crates/zeroclaw-runtime/src/skillforge/` |
| [backends/curated.py](backends/curated.py) | ironclaw 模式实现 | `src/tools/builtin/skill_tools.rs` + `wit/tool.wit` |
| [fixtures/catalog/](fixtures/catalog/) | forage 的"外部 catalog" 模拟 | 真 zeroclaw 走 GitHub / ClawHub |
| [fixtures/approved/](fixtures/approved/) | curated 的"已审 skill" 模拟 | 真 ironclaw 走 PR review + signatures |
| [main.py](main.py) | 4 场景驱动 | — |

## fixtures 长啥样

`fixtures/catalog/`（forage 模式扫的源）：
- `code-style-rate-limited.md` —— score 0.85（高）
- `wasm-component-skill.md` —— score 0.78（高）
- `json-output-pretty.md` —— score 0.72（中）
- `low-quality-skill.md` —— score 0.32（低，应该被刷掉）

`fixtures/approved/`（curated 模式的已审仓库）：
- `secure-file-write.md` —— signed_by=`ironclaw-team`, capabilities=`[workspace-write, log]`
- `http-client-best-practices.md` —— signed_by=`verified-author-1`, capabilities=`[http-request, log]`
- `sketchy-skill-unsigned.md` —— 无签名 + 申请 `exec-shell` 等危险能力（应该被拒）

## 观察题目

1. 跑场景 1，对比三种 registry 的产出："source" 字段分别是 `auto-evolved` / `github:...` / `ironclaw-bundled`——这个字段决定了**审计能不能追到源头**。如果你的产品被监管要求"每条 skill 都能追溯"，哪种哲学满足？
2. 场景 2 调低阈值到 0.2，烂 skill 就装进来了。换句话说 forage 模式的安全等价于**评分模型的质量**。生产里评分要写成什么样才不容易被作弊？
3. 场景 3 里 `sketchy-skill-unsigned` 被拒了两次（无签名 + 申请危险能力）。如果作者只是无签名但能力清单合规，应该拒吗？如果合规但申请了 `exec-shell`，应该拒吗？想清楚 curated 的拒绝边界。
4. 场景 4 看三种 prompt 长度。**哪种最容易撑爆 system prompt**？怎么补救？（提示: 索引模式 + 按需 view, 参考 case 01）
5. 想加第四种哲学（比如"中心化 review by AI agent"——LLM 审 LLM 写的 skill），要新增哪些方法到 `SkillRegistry` ABC？

## 跟其它 case 的关系

- [case 01](../../01-hermes-skill-evolution): 自产模式（hermes）的纯粹深度拆解
- [case 03](../../03-openhands-sandbox-isolation): 多后端抽象的实际工程模板（`SandboxService` ABC），本 case 的 `SkillRegistry` 模仿同一模式
- [case 04](../../04-openhands-event-callbacks): 类似的"插件式 processor + 双维度过滤"思路, 但用在事件副作用
