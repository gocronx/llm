# Demo —— Event-sourced 对话最小复刻

约 200 行 Python 复刻 OpenHands 的核心机制之一：**事件溯源对话状态**。

## 为什么不写 FastAPI server

OpenHands 真实代码里有 App Server / Agent Server / Sandbox 三层进程，复刻全套要写好几百行。但**最值得让你"看见"的不是服务器形态，是事件流如何承载对话状态**——这点用 CLI 跑两次就讲清楚了，没必要起服务器。

服务器形态怎么搭其实很简单：拿现成的 FastAPI 把 `main.py` 的 `send_message` 包成 POST 接口就行（README 末尾有 30 行示例）。

## 跑法

```bash
cp ../.env.example .env  # 在 case 根目录
pip install -r requirements.txt
```

然后跑这 4 条命令体验"重启复活"：

```bash
# 第一次: 跟一个新对话讲个偏好
python main.py session-a "记住我喜欢用 ramen 当用户名占位符"

# 第二次: 让模型用这个偏好 (Python 是新进程, 状态从磁盘 replay 出来)
python main.py session-a "给我写个 flask hello world, 用我的占位符"

# 看磁盘上的事件流长啥样
python main.py session-a --inspect

# 再开一次, 模型仍然知道占位符是 ramen
python main.py session-a "再写一个 fastapi 版本, 用同样的占位符"
```

每次 `python main.py ...` 都是**全新 Python 进程**。如果用 hermes 这种内存模式，第二次跑模型完全不知道你说过 ramen。OpenHands 模式下事件流在磁盘上，新进程 replay 一遍就回到状态。

## 其它命令

```bash
python main.py --list                    # 看磁盘上有哪些对话
python main.py session-a --clear          # 清空这个对话
python main.py --clear-all                # 清空全部 (.events/)
```

## 文件分工

| 文件 | 对应 OpenHands 哪段 |
|------|--------------------|
| [events.py](events.py) | `openhands/app_server/event/event_service.py` 的 `FilesystemEventService` |
| [replay.py](replay.py) | Agent Server 启动时 replay 历史的逻辑 |
| [main.py](main.py) | App Server 的 `send_message` endpoint + Agent Server 的 ReAct loop（合并简化版） |

砍掉的部分（跟"事件溯源"机制无关，只是工程化）：
- 不分 App Server / Agent Server 双进程：单 CLI 进程合并演示
- 不接 sandbox：工具调用直接没实现，demo 只跑文本对话
- 不接 WebSocket / SSE：CLI 输出代替前端流式
- 不接云存储后端：只 Filesystem
- 不接 event_callback：没有"事件触发后续动作"的钩子
- 不做 snapshot：每次都全量 replay (事件少的时候没事，多了要补)

## 手玩

事件文件就是 `.events/<conv_id>/*.json`，可以直接 cat 看。
也可以手编一条事件文件再跑，看 replay 是否吃这条手编的。
这就是 event sourcing 的核心承诺：**磁盘是真相**。

## 升级到 FastAPI 服务器版本（参考）

如果你想把 demo 也包成 server 形态体验 App Server 那一层，加这么个 `server.py` 即可：

```python
# server.py
from fastapi import FastAPI
import events
from replay import replay_to_messages
# ...复用 main.py 里的 _make_client

app = FastAPI()

@app.post("/conversations/{cid}/messages")
def send(cid: str, body: dict):
    events.append(events.Event(
        kind="user_message", conversation_id=cid,
        payload={"text": body["text"]},
    ))
    messages = [{"role": "system", "content": "..."}] + replay_to_messages(cid)
    # ... 调 LLM, append assistant_message, return reply
    return {"reply": reply, "event_count": len(events.load_all(cid))}

@app.get("/conversations/{cid}/events")
def get_events(cid: str):
    return [{"kind": e.kind, "payload": e.payload, "ts": e.timestamp}
            for e in events.load_all(cid)]
```

跑 `uvicorn server:app --port 8001`，然后 `curl -X POST localhost:8001/conversations/foo/messages -d '{"text":"..."}'`。

**关键观察**：杀掉 uvicorn 进程，再启动一次，对话状态完全不丢——因为状态压根不在进程内，在 `.events/` 磁盘上。

## 观察题目

跑完想想：
1. 如果有两个 client 同时往一个 conversation_id 写消息会发生什么？事件 id 会撞吗？文件名会撞吗？（提示：看 `events.py` 的文件名规则）
2. 把 `temperature` 调高反复跑同一句，事件文件越来越多。怎么实现一个"分支对话"（同一个父事件下两条不同 reply）？
3. 假如你想给会话挂个钩子"每次有新消息就更新对话标题"——你会在哪里加这段逻辑？（参考 OpenHands 的 event_callback 模块）
4. replay 10000 条事件要多久？什么时候需要 snapshot 机制？
