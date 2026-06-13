"""
统一版本号管理 —— 单一数据源为 backend/pyproject.toml。

用法:
    from config.version import APP_VERSION
    print(APP_VERSION)  # "1.0.0"
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # noqa: F401  # pragma: no cover


def _read_version() -> str:
    """从 pyproject.toml 读取版本号"""
    # PyInstaller 打包后，pyproject.toml 不在标准位置，使用硬编码回退
    if getattr(sys, "frozen", False):
        return "1.0.0"

    # 开发模式：从 backend/pyproject.toml 读取
    config_dir = Path(__file__).resolve().parent  # config/
    pyproject = config_dir.parent / "pyproject.toml"  # backend/pyproject.toml
    if pyproject.exists():
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            version = data.get("project", {}).get("version", "1.0.0")
            return version
        except Exception:
            pass

    return "1.0.0"


APP_VERSION = _read_version()
