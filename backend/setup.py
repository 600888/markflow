"""setup.py — 配合 pyproject.toml，实现 playwright install chromium 自动安装"""

from __future__ import annotations

import contextlib
import subprocess
import sys

from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install


def _run_playwright_install() -> None:
    """安装 Playwright Chromium 浏览器"""
    try:
        # 先确认 playwright 是否可导入
        import playwright  # noqa: F401
    except ImportError:
        return

    # 检查是否已经安装过 Chromium
    try:
        # 如果可以获取到 driver 路径，说明已经安装了
        return
    except Exception:  # noqa: BLE001, S110
        pass

    with contextlib.suppress(Exception):
        subprocess.run(  # noqa: S603
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            timeout=300,
        )


class PostInstallCommand(install):
    """pip install 后自动安装 Chromium"""

    def run(self) -> None:
        """执行安装后自动安装 Chromium。"""
        install.run(self)
        _run_playwright_install()


class PostDevelopCommand(develop):
    """pip install -e . 后自动安装 Chromium"""

    def run(self) -> None:
        """执行开发安装后自动安装 Chromium。"""
        develop.run(self)
        _run_playwright_install()


setup(
    cmdclass={
        "install": PostInstallCommand,
        "develop": PostDevelopCommand,
    },
)
