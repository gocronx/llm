# 12 · Hybrid Search Demo

代码库检索：**grep（精确符号）+ vector（语义）+ 加权融合**。

| query 类型 | 推荐 |
|---|---|
| 字面符号（"def login"） | grep |
| 语义意图（"how to authenticate"） | vector |
| 兼有（"database connection"） | hybrid |

## 跑起来

```bash
cd python
pip install -r requirements.txt
python test.py
python main.py
```

## 共通的坑

- ❌ 只用 grep → 找不到改名的函数
- ❌ 只用 vector → 字面 token 搜不准
- ❌ 不按文件聚合 → 同文件多份分数
- ⚠️ alpha 拍脑袋 → 用真实查询日志校准
