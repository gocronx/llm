# 14 · Skill Loader Demo

Anthropic Skills 的本地实现。把"指令 + 触发条件 + 正文"打包成 `SKILL.md`，按用户请求选相关 skill 注入 system，不相关的不占 context。

## 三种路由

| 策略 | 选谁 | LLM 调用 |
|---|---|---|
| keyword | 规则命中 | 0 |
| llm | 小调用挑名字 | +1 |
| implicit | 主 LLM 通过 tool 自己加载 | 嵌主对话 |

## 跑起来

```bash
cd python
pip install -r requirements.txt
python test.py    # 8/8 passed
python main.py    # 三种策略对照
```

## 共通的坑

- ❌ skill body 太长 → 多加载几个就爆 context
- ❌ trigger 只有一种语言 → 用户用同义词匹配不上
- ❌ implicit 模式没 max_iters → 主 LLM 反复 skill_view
- ❌ route_llm 让模型输出"理由" → 越说越漂；只让出 JSON 数组
