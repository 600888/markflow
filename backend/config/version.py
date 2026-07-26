"""
MarkFlow version management.

The single source of truth is ``backend/pyproject.toml``. PyInstaller bundles
that file beside the frozen Python runtime so development and packaged builds
report the same version.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path


def _pyproject_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "pyproject.toml"  # type: ignore[attr-defined]  # noqa: SLF001
    return Path(__file__).resolve().parent.parent / "pyproject.toml"


def _read_version() -> str:
    try:
        with _pyproject_path().open("rb") as file:
            return str(tomllib.load(file)["project"]["version"])
    except (FileNotFoundError, KeyError, OSError, tomllib.TOMLDecodeError):
        return "0.0.0"


APP_VERSION = _read_version()
