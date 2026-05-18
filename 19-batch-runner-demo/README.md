# 19 · Batch Runner Demo

跑 1 万条 prompt 的最小可靠实现：**并发 + 重试 + 断点续跑 + 增量落盘**。生产里所有的离线评测、数据生成、批量 inference 都长这个样子。

## 三件大事

| 件 | 怎么做 |
|---|---|
| 并发 | ThreadPool（默认 4，可调） |
| 重试 | tenacity 指数退避，TransientError 重试 3 次；4xx 不进 |
| 续跑 | output JSONL 里 error=None 的 id 算 done，重启跳过；失败 id 重跑 |

## 跑起来

```bash
cd python
pip install -r requirements.txt
python test.py    # 6/6 passed
python main.py
python main.py    # 再跑：自动续
python main.py --no-resume
```

## 共通的坑

- ❌ 失败也算 done → 再跑时不会重试失败 id
- ❌ 4xx 也重试 → 浪费
- ❌ 并发开到 100 → 服务端限流
- ❌ 批量 write → crash 时丢一批；单条 append 最稳
