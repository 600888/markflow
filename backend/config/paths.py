"""路径配置"""

from __future__ import annotations

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 打包后，所有数据解压到 _MEIPASS（对应 backend/ 目录）
    DATA_ROOT = Path(sys._MEIPASS)  # type: ignore[attr-defined]  # noqa: SLF001
    TEMPLATES_DIR = DATA_ROOT / "templates"
    FILTERS_DIR = DATA_ROOT / "filters"
else:
    # 开发模式：项目根目录（markflow/）
    DATA_ROOT = Path(__file__).resolve().parent.parent.parent
    TEMPLATES_DIR = DATA_ROOT / "backend" / "templates"
    FILTERS_DIR = DATA_ROOT / "backend" / "filters"

# 日志目录（markflow/logs/ 或 _MEIPASS/logs/）
LOG_DIR = DATA_ROOT / "logs"

# 测试数据目录（markflow/data/ 或 _MEIPASS/data/）
DATA_DIR = DATA_ROOT / "data"
