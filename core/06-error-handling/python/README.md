# 06 · Error Handling — 重试 + 退避 + Retry-After + Circuit Breaker + Fallback

**一个 `Resilient` 类把 LLM 调用的四件挡灾事做完：1) 网络/5xx/429 重试 + 指数退避 jitter；2) 尊重 Retry-After；3) 连错 N 次进 circuit breaker；4) primary 挂了 fallback secondary。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `resilient.py` | 🟢 套出去用 | `Resilient([Endpoint, Endpoint])` + `Breaker` |
| `fakesrv.py` | 🟢 测试套件（套出去就改 base_url） | 本地 stdlib HTTP，按脚本返回 200/429/500 |
| `main.py` | demo only | 四个场景：retry / Retry-After / fallback / breaker |
| `test.py` | demo only | 确定性单元测试 |

## 哪些异常算可重试

OpenAI SDK 帮你把 HTTP 错误分门别类成 Python 异常，不用看 status_code：

| 异常 | 含义 | 处理 |
|---|---|---|
| `APIConnectionError` | TCP 断了 / DNS 挂了 | 退避后重试 |
| `APITimeoutError` | 客户端等超时 | 退避后重试 |
| `RateLimitError` | 429 | 优先 Retry-After，否则退避 |
| `APIStatusError(4xx 非 429)` | 参数错 / 鉴权错 | 不重试（重试也是错） |
| `APIError` | 兜底 | 不重试，保守 |

## Circuit Breaker 三态

```
closed (正常)
  └─ 连续失败达到 threshold ─> open (拒绝请求)
                                  └─ cooldown 过后 ─> half-open (放一次试探)
                                                          ├─ 成功 -> closed
                                                          └─ 失败 -> open
```

`Breaker.allow()` 是非阻塞判断 —— 不要 sleep，让调用方决定要不要 fallback。

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py     # 4/4 passed
python main.py     # 看四个场景的事件流
```

`test.py` 不依赖外网，全靠 fakesrv 本地跑。

## 关键设计点

| 决策 | 原因 |
|---|---|
| 不引 tenacity / pybreaker | 80 行自己写更清楚；依赖也更轻 |
| 用 OpenAI SDK 的异常类而不是 status_code | SDK 已经分门别类，比看 401/429/500 干净 |
| Jitter（`0.5 + random/2`） | 一群客户端同时重试会再次打挂服务端，jitter 抹平 |
| `Endpoint.breaker` 每个 endpoint 独立 | primary 挂了开 breaker 不影响 secondary 计数 |
| `on_event` 回调 | 把日志决策（打不打、打到哪）留给调用方，不在库里 print |

## 常见坑

- ❌ **重试 4xx 非 429** —— 参数错重试也是错，越重试越浪费
- ❌ **不带 jitter 的指数退避** —— 一群客户端同步复试，再次打挂服务端（thundering herd）
- ❌ **breaker 全局一份** —— primary 挂了顺便把 secondary 也禁了；要每个 endpoint 一个
- ❌ **429 不看 Retry-After** —— 服务端告诉你等 30s 你 1s 就来，照样被禁
- ❌ **breaker.allow() 内部 sleep** —— 阻塞调用线程，应该让上层决定 fallback
- ⚠️ **`response.headers` 在 SDK 异常里的位置** —— 不同版本 SDK 暴露方式不同，`getattr(exc, "response", None)` 是稳的兼容写法
