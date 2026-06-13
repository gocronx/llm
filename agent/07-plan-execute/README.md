# 07 · Plan-and-Execute

跟 [01-simple](../01-simple) 的 ReAct 对着看：ReAct 每轮才想下一步，这个先把整件事拆成一份计划，再照着做。

<p align="center"><img src="assets/07-plan-execute-illustrations/02-overview-card.png" width="420" alt="先列计划再照着做（知识卡）"></p>

## 跟 ReAct 差在哪

ReAct 是走一步看一步：每轮都让 LLM 重新判断"现在该干嘛"。任务步数一多，这种反复判断既费 token，也容易跑着跑着忘了最初要干嘛。

Plan-Execute 把这件事拆成两段。先让 LLM 一次性把目标拆成有序步骤（planner），然后一条条执行（executor），中间不再每步都重新发散。

```
goal ──► planner ──► [步骤1, 步骤2, 步骤3]
                          │
            ┌─────────────┴──────────────┐
            ▼                             ▼
        executor 逐步做            做完一步回头看
        (每步带工具)              要不要改剩下的 (replan)
            │                             │
            └─────────────┬───────────────┘
                          ▼
                    synthesizer 汇成最终答案
```

三个角色都是同一个 LLM，靠 system prompt 区分：planner 出计划、executor 干活、synthesizer 收尾。

## replan 才是重点

只"先列计划再执行"的话，本质就是念一遍待办清单——现实里第一步的结果常常推翻后面的安排。比如计划是"查深圳天气 → 推荐户外产品"，结果查出来在下雨，那"推荐户外产品"这步就得改成室内的。

所以每做完一步，把真实结果喂回去问 LLM：剩下的步骤还成立吗？让它删、改、加。`replan=False` 时退化成静态计划，可以开关对比着看。

代码里两处兜底：

- 改计划时如果模型输出解析不出来（`_parse` 返回 `None`），沿用旧计划，别把进度搞丢
- `max_steps` 封顶，避免反复 replan 越改越多停不下来

## 目录

```
.
├── python/
│   ├── planner.py   # 出计划 + 改计划，JSON 宽松解析
│   ├── agent.py     # PlanExecuteAgent：规划→执行→replan→汇总
│   ├── tools.py     # 跟 01 同一套工具，方便对比
│   ├── main.py / test.py
│   └── requirements.txt
├── .env.example
└── README.md
```

## 跑起来

```bash
cd python
cp ../.env.example ../.env   # 填好 API_KEY / MODEL_ID
pip install -r requirements.txt
python test.py    # 6/6，mock LLM 测规划/执行/replan，不联网
python main.py    # 3 个多步任务
```

## 什么时候用它，什么时候别用

适合步骤多、前后有依赖、值得先理清顺序的任务。不适合简单一两步就能答的——那种 ReAct 更省事，多一个 planner 调用纯属浪费。

planner 把计划定死也有代价：第一步规划得不好，后面全歪。所以 replan 不是锦上添花，是这个范式能不能用的关键。真要追求每步都重新评估、还带回溯打分，那是 [ToT / LATS](../README.md#一单-agent-推理范式) 的活，比这个重得多。

![小黑一手举着清单照着做、做完的打勾，一手用铅笔改还没做的部分](assets/07-plan-execute-illustrations/01-plan-then-execute.png)
