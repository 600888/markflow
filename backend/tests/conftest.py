"""共享测试夹具"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_markdown() -> str:
    """测试用 Markdown 内容"""
    return """# 标题

这是一段 **加粗** 文本。

- 列表项 1
- 列表项 2

```python
print("hello")
```
"""
