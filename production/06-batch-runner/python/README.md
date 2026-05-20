# 19 · Batch Runner — 并发 + 重试 + 断点续跑

**批量跑 LLM 调用（标注、清洗、向量化前处理）的最小可靠实现：
ThreadPool 并发 + tenacity 指数退避 + JSONL output 续跑。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `batch.py` | 🟢 套出去用 | `Job` / `Result` / `run_one` / `run_batch` + 重试 + checkpoint |
| `main.py` | demo only | CLI 包装 |
| `test.py` | demo only | 6 个 mock 测试，不调外网 |
| `data/sample.jsonl` | demo 数据 | 一行一个 `{"id":"...","prompt":"..."}` |

## 三件大事

1. **并发**：ThreadPool（IO-bound），默认 4，可调 `--concurrency 16`
2. **重试**：tenacity，TransientError（5xx / 429 / 网络）退避 1-8 秒，最多 3 次；4xx 不重试
3. **断点续跑**：output JSONL 里 `error == None` 的 id 视为已完成，重启跳过

**失败的 job 不算 done**，重启会重跑 —— 不要 silently 把 error 当 success 写盘。

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py                      # 6/6 passed
python main.py --limit 5            # 只跑前 5 个
python main.py --concurrency 8      # 全跑
python main.py                      # 第二次跑：自动从 output 续
python main.py --no-resume          # 清掉 output 从头跑
```

输出 JSONL 每行一个 `Result`：

```json
{"id":"q1","prompt":"...","answer":"...","error":null,"elapsed_ms":420,"attempts":1,"tokens":35}
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| append-only output JSONL | 没写完崩了，已成功的不丢；重启读最后一行就知道进度 |
| 失败的 job 也写 output（带 error） | 审计：哪些 job 失败、为什么；下次重启自动重试 |
| `load_done` 只算 error=None | 失败 id 算"未完成"，重启会重跑 |
| tenacity 退避 `min=1, max=8` 指数 | 短到能恢复，长到不无限耗时；4xx 不进重试 |
| `TransientError` 单独类型 | 让 tenacity 通过 `retry_if_exception_type` 精确匹配，4xx 自然不进 |
| 进度行带 `elapsed / eta` | 跑几千个 job 时不靠这个看进度会哭出来 |

## 常见坑

- ❌ **失败也算 done** —— 用户发现没全跑完想重跑，结果失败 id 被跳过
- ❌ **不带 timeout** —— 一个 hung 的 job 会卡住整个 pool slot
- ❌ **并发开到 100** —— 服务端限流 / 本地连接耗尽；从 4 开始压
- ❌ **4xx 也重试** —— 参数错重试 3 次也是错，纯浪费
- ❌ **批量写 output 用 batch write** —— 一次写 100 条，崩了就丢；单条 append 最稳
- ⚠️ **`max_workers` 不等于实际并发** —— 服务端有连接池上限，超过后请求排队（看似并发实际串行）
