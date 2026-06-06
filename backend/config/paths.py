"""路径配置"""

from __future__ import annotations

from pathlib import Path

# 项目根目录（markflow/，即 backend/ 的父目录）
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# 日志目录（markflow/logs/）
LOG_DIR = ROOT_DIR / "logs"
