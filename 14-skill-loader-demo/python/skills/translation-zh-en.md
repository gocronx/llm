---
name: translation-zh-en
description: Translate between Chinese and English with attention to tone, idioms, and technical terminology.
triggers: [translate, translation, 翻译, 中译英, 英译中, en2zh, zh2en]
---

When the user asks for translation:

技术术语：
- 保留通用英文术语不翻译（API、JSON、Token、Pull Request）
- 如果是初次出现且对方可能不熟，加括号注解：`闭包（closure）`

风格：
- 默认翻译要"达意 + 流畅"，不强求字面对应
- 如果是文档/正式文本，保持原文语气
- 如果是口语/聊天，用对应语言的口语化表达
- 中→英时避免中式英语（"do well in" → "excel at"）

格式：
- 只输出译文，不解释（除非用户明确要解释）
- 如果原文有 Markdown 格式，译文保留格式
- 不要无理由加省略号或感叹号

当用户没有提供要翻译的文本：
- 用一句话要求贴文本，例如："请提供要翻译的内容。"
- 不要寒暄、不要演示样例
