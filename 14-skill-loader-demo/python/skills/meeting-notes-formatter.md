---
name: meeting-notes-formatter
description: Turn raw meeting transcripts into structured action items with owners and deadlines.
triggers: [meeting, notes, transcript, action items, 会议, 纪要, 待办, 行动项]
---

When the user provides raw meeting notes or a transcript, structure the output as:

## 决策（Decisions）
- 列出本次会议明确做出的决策，每条一行。

## 行动项（Action Items）
| 任务 | 负责人 | 截止日期 |
|------|--------|---------|
| ... | ... | ... |

## 待跟进（Open Questions）
- 列出未决议、需要后续讨论的事项。

规则：
- 如果原文没有明确截止日期，写"未定"，不要凭空捏造
- 如果原文没有提到负责人，写"未指定"
- 不要把"讨论了 X"自动转成"决定了 X"

当用户没有提供原文（如只说"把这段录音整理一下"但没贴文字稿）：
- 用一句话指出缺什么，例如："请先提供文字稿才能整理。"
- 不要预告输出格式
- 不要寒暄、不要写"我已准备好帮您"
