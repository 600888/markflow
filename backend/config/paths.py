"""路径配置"""

from __future__ import annotations

import os
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

# data 目录：优先使用 Tauri 传入的 MARKFLOW_DATA_DIR（打包后），
# 否则使用项目目录下的 data/（开发模式）或 _MEIPASS/data/（PyInstaller 内嵌）
_env_data = os.environ.get("MARKFLOW_DATA_DIR")
if _env_data:
    DATA_DIR = Path(_env_data)
else:
    DATA_DIR = DATA_ROOT / "data"
