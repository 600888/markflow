"""结构化日志配置"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """初始化日志格式"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        stream=sys.stdout,
    )
