---
name: sql-query-builder
description: Help write, review, or optimize SQL queries. Cover joins, aggregations, window functions, and explain plans.
triggers: [sql, query, join, group by, postgres, mysql, 查询, 数据库]
---

When the user asks about SQL：

写查询时：
- 默认用 ANSI SQL；如果用户指定方言（PostgreSQL / MySQL / SQLite）就用对应方言
- 显式列出字段名，不要用 `SELECT *`
- 多表 JOIN 时给表加别名，引用字段用 `t.col` 而不是 `col`
- 涉及聚合时一定要带 `GROUP BY`，不要依赖 MySQL 的宽松模式

优化查询时：
- 先问能不能给出 `EXPLAIN` 输出
- 检查：缺索引、全表扫描、N+1 模式、SELECT *、不必要的子查询
- 建议先看执行计划再动手，不要凭直觉加索引

输出格式：
- 代码块用 ```sql 标记
- 重要的列、索引、JOIN 条件用注释标出
- 给出查询后简要说明每一段在做什么

当用户的请求**完全模糊**（如只说"写个查询"、"帮我查询"，没说要查什么）：
- 用一句话要求关键信息，例如："请说明要查询的表结构和目的。"
- 不要预告 SQL 模板或骨架
- 不要寒暄

但如果**任务清晰只是缺表结构**（如"找出过去 7 天下单超过 3 次的用户邮箱"）：
- 用合理默认假设直接写（如表名 `orders`、字段 `user_email`、`order_date`）
- 在注释或末尾标注假设："// 假设表名为 orders、字段为 user_email"
- 不要拦下来问 schema
