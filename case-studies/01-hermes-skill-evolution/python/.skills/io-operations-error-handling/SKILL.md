---
description: For file/network/IO operations, always wrap in try/except with logging, no verbose comments
---

## IO Operations Error Handling Pattern

**Trigger**: Any file I/O, network request, or blocking IO operation

**Requirements**:
1. Wrap in `try/except` with specific exception handling
2. Add `logging` for success and error paths
3. No verbose explanatory comments - code should be self-explanatory

**Template**:
```python
import logging

logging.basicConfig(level=logging.INFO)

try:
    # IO operation here
    with open('/path/file.txt', 'w') as f:
        f.write('data')
    logging.info('Operation succeeded')
except IOError as e:
    logging.error(f'Operation failed: {e}')
```

**Key points**:
- Use specific exceptions (`IOError`, `ConnectionError`, etc.) before generic `Exception`
- Log meaningful messages with context
- Keep comments minimal - only for non-obvious logic
