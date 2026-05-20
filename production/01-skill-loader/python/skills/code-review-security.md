---
name: code-review-security
description: Review code with a focus on security vulnerabilities (injection, auth, secrets, unsafe deserialization).
triggers: [review, code review, security, vulnerability, subprocess, shell, injection, 审查, 安全, 代码审查, 漏洞]
---

When the user asks you to review code, focus specifically on security issues. Check in this order:

1. **注入风险**
   - SQL 拼接（用参数化查询替代）
   - 命令注入（subprocess shell=True、os.system）
   - XSS（HTML 渲染未转义）

2. **认证与授权**
   - 密码明文存储、弱哈希（MD5/SHA1）
   - 权限校验缺失或顺序错（先操作再校验）
   - JWT secret 硬编码

3. **秘密泄露**
   - 代码里写死的 API key / 密码 / token
   - 日志打印敏感字段
   - 错误信息泄露内部细节

4. **反序列化**
   - pickle、yaml.load 不安全
   - JSON schema 校验缺失

输出格式：
- 按严重度排序（critical / high / medium / low）
- 每条给出：`文件:行号 → 问题 → 建议修复`
- 不要列"一般性建议"（变量命名、风格等），只关心安全

当用户没有提供具体代码（如只说"审查我的代码"但没贴代码片段）：
- 用一句话要求贴代码，例如："请贴出要审查的代码片段。"
- 不要预告审查报告的格式
- 不要寒暄
