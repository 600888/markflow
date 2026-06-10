"""路径配置"""

from __future__ import annotations

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 打包后，数据解压到 _MEIPASS（templates/filters 在 exe 内打包）
    DATA_ROOT = Path(sys._MEIPASS)  # type: ignore[attr-defined]  # noqa: SLF001
    TEMPLATES_DIR = DATA_ROOT / "templates"
    FILTERS_DIR = DATA_ROOT / "filters"
    # 日志写入 exe 同级 logs 目录
    LOG_DIR = Path(sys.executable).parent.resolve() / "logs"
else:
    # 开发模式：项目根目录（markflow/）
    DATA_ROOT = Path(__file__).resolve().parent.parent.parent
    TEMPLATES_DIR = DATA_ROOT / "backend" / "templates"
    FILTERS_DIR = DATA_ROOT / "backend" / "filters"
    LOG_DIR = DATA_ROOT / "logs"

# 测试数据目录（markflow/data/ 或 _MEIPASS/data/）
DATA_DIR = DATA_ROOT / "data"
