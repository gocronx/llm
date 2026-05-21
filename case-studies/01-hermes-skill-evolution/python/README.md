# Demo —— Post-turn Reflection Loop 最小复刻

100 多行 Python 复现 hermes-agent 的"越用越聪明"。

## 跑法

```bash
cp ../.env.example .env  # 在 case 根目录
pip install -r requirements.txt
python main.py
```

第一遍跑会:
1. 清空 `.skills/`（确保从干净状态开始）
2. **Round 1**: 用户问写文件代码，再说"以后默认带 try/except 不要说教"
3. **后台复盘**: reviewer LLM 看完 transcript，决定是否产 skill
4. **Round 2**: 新 system prompt（带刚产生的 skill），用户问读 JSON。看模型是否自动遵守上轮偏好

期望：Round 2 的输出**自动带 try/except + logging，不啰嗦**。

## 文件分工

| 文件 | 对应 hermes 哪段 |
|------|-----------------|
| [skills.py](skills.py) | `agent/prompt_builder.py:988` `build_skills_system_prompt` + `tools/skill_manager_tool.py:465` `skill_manage` |
| [reviewer.py](reviewer.py) | `run_agent.py:4077` `_SKILL_REVIEW_PROMPT` + `run_agent.py:4312` `_spawn_background_review` |
| [main.py](main.py) | `run_agent.py:15653` 触发逻辑 + 主对话循环 |

砍掉的部分（跟"学习"机制无关，只是工程化）：
- 不开真的后台线程：同步跑方便观察
- 不实现 LRU + mtime cache：skill 数量少
- 不分 references/templates/scripts：单 SKILL.md 够看清原理
- 不做 platform 维度 / 多用户 / disabled 列表

## 手玩

`.skills/<skill-name>/SKILL.md` 可以手编。改完再跑一次 Round 2 看变化。
也可以 `python main.py --clear` 清空 skill 库，从头再来。

## 观察题目

跑完想想：
1. reviewer 写出来的 skill `description` 字段够不够泛化？（hermes prompt 强调 class-level 不是 session-specific）
2. 如果连续跑两次 Round 1，skill 会被覆盖、追加、还是产生第二个？
3. 把 reviewer 的 `temperature` 调高到 1.0，skill 的稳定性怎么变？
4. 故意输入一个 "为什么 ls 命令找不到？" 这种环境问题，reviewer 会不会上当记成 skill？（hermes prompt 的反例清单就是防这个）

带着问题去玩，比读 README 收获大。
