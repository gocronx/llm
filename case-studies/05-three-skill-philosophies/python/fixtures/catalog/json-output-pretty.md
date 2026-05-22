---
name: json-output-pretty
description: Format JSON outputs with 2-space indent and sorted keys
source: github:dev-utils/skills-catalog
score: 0.72
---

# Pretty JSON output

When writing code that prints or saves JSON, default to:

```python
json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
```

Rationale: human-readable diffs, stable git history, multilingual support.

For files: use `json.dump(..., indent=2, sort_keys=True, ensure_ascii=False)` with explicit `encoding="utf-8"`.

Avoid `json.dumps(data)` (single line, unicode escapes, unsorted keys) unless serialization size matters.
