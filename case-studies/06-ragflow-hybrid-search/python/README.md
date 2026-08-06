# BM25 + 向量混合检索 —— RAGFlow 最小复刻

0 外部依赖。纯内存跑，演示"两路召回 + 加权融合"的设计思想。

```bash
pip install -r requirements.txt
python test.py   # 9 个单测
python main.py
```

## 跟 RAGFlow 原版比

原版 BM25 委托给 ES/OS 倒排索引（生产级毫秒级），本 demo 用纯 Python
自实现 BM25 公式——教学用，能让看到 BM25 在算什么。详见 `BENCHMARK.md`。
