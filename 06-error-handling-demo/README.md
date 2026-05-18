# 06 · Error Handling Demo

LLM 调用挡灾的四件事打包：**重试 + 退避 + Retry-After + Circuit Breaker + Fallback**。Python 单语言，因为生产里基本都是 Python 跑挡灾代理（vLLM、LiteLLM 等都是 Python）。

## 四件事各管什么

| 事 | 解决的问题 |
|---|---|
| 指数退避 + jitter | 网络抖动 / 5xx 间歇性 / 429 限流 → 等一会儿大概率就好 |
| `Retry-After` 头 | 服务端明确告诉你等多久，比客户端瞎猜准 |
| Circuit Breaker | endpoint 真挂了，重试只是浪费 → 短路一段时间，让上游 fallback |
| Fallback Chain | primary 挂了切 secondary（不同 model / 不同 provider） |

## 目录

```
.
├── python/
│   ├── resilient.py   # 🟢 Resilient + Breaker + Endpoint
│   ├── fakesrv.py     # 🟢 本地可脚本化 HTTP 服务
│   ├── main.py / test.py
│   └── requirements.txt
└── README.md
```

## 跑起来

```bash
cd python
pip install -r requirements.txt
python test.py    # 4/4 passed，不依赖外网
python main.py    # 四个场景的事件流
```

## 关键设计点（详见 `python/README.md`）

- 用 OpenAI SDK 的异常类分类，不看 status_code
- Jitter 抹平 thundering herd
- 每个 endpoint 一个 breaker，互不影响
- breaker.allow() 非阻塞，sleep 决策交给调用方
- fakesrv 让测试完全确定性，不需要真 LLM

## 共通的坑

- ❌ 重试 4xx 非 429
- ❌ 退避不带 jitter → thundering herd
- ❌ breaker 全局一份 → primary 挂了把 secondary 也禁了
- ❌ 429 不看 Retry-After
