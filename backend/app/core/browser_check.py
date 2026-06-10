"""
Chromium 浏览器检测与自动安装

在 PyInstaller 打包后，playwright Python 库被打进 exe，
但 Chromium 浏览器二进制 (~200MB) 不包含在安装包中。
此模块负责检测 Chromium 是否可用，并在需要时自动下载。

用法:
    from app.core.browser_check import ensure_chromium, is_chromium_ready, get_install_progress

    ok = await ensure_chromium()
    progress = get_install_progress()  # {"progress": 45, "stage": "downloading", "message": "..."}
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from app.core.log import log

# ── 模块级缓存 ──────────────────────────────────────────
# None = 未检测, True = 可用, False = 不可用
_CHROMIUM_READY: bool | None = None

# 安装进度跟踪（可供 SSE 轮询）
_INSTALL_PROGRESS: dict[str, object] = {
    "progress": 0,
    "stage": "idle",
    "message": "",
}


def get_install_progress() -> dict[str, object]:
    """获取当前安装进度"""
    return dict(_INSTALL_PROGRESS)


def _set_install_progress(progress: int, stage: str, message: str) -> None:
    """更新安装进度"""
    _INSTALL_PROGRESS["progress"] = progress
    _INSTALL_PROGRESS["stage"] = stage
    _INSTALL_PROGRESS["message"] = message
    log.info(f"[install] {progress}% - {message}")


def _check_chromium_sync() -> bool:
    """同步执行 Chromium 检测（在独立线程中运行）"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("playwright 未安装")
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
            )
            browser.close()
    except Exception:
        log.warning("Chromium 浏览器不可用")
        return False

    return True


def is_chromium_ready() -> bool:
    """
    快速检查 Chromium 是否可用（使用缓存结果，不重复启动浏览器）

    注意：仅检查缓存 + 模块导入性，不实际启动浏览器。
    需要真实检测请使用 get_or_check_chromium()。
    """
    global _CHROMIUM_READY  # noqa: PLW0603
    if _CHROMIUM_READY is not None:
        return _CHROMIUM_READY

    try:
        import playwright  # noqa: F401
    except ImportError:
        _CHROMIUM_READY = False
        return False

    return False


def get_or_check_chromium() -> bool:
    """获取缓存状态，若未检测过则在线程中执行浏览器检测"""
    global _CHROMIUM_READY  # noqa: PLW0603
    if _CHROMIUM_READY is not None:
        return _CHROMIUM_READY

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_check_chromium_sync)
            _CHROMIUM_READY = future.result(timeout=30)
    except Exception:
        _CHROMIUM_READY = _check_chromium_sync()

    if _CHROMIUM_READY:
        log.info("Chromium 浏览器检测通过")
    return _CHROMIUM_READY


def _install_chromium_sync() -> bool:
    """同步安装 playwright 包并下载 Chromium 浏览器（分步更新进度）"""
    _set_install_progress(0, "starting", "准备安装...")
    start = time.monotonic()

    # 第 1 步：安装 playwright Python 包
    _set_install_progress(5, "install_package", "正在安装 playwright Python 包...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "playwright"],
            capture_output=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()[:500]
            log.error(f"安装 playwright 包失败: {stderr}")
            _set_install_progress(0, "failed", f"安装 playwright 包失败: {stderr[:100]}")
            return False
    except (subprocess.TimeoutExpired, OSError) as e:
        log.error(f"安装 playwright 包异常: {e}")
        _set_install_progress(0, "failed", f"安装 playwright 包异常: {e}")
        return False

    _set_install_progress(20, "download_chromium", "正在下载 Chromium 浏览器 (~200MB)...")

    # 第 2 步：下载 Chromium 浏览器（SSE 端点会定时轮询进度）
    # playwright install 的输出通过管道不可靠解析，安装期间由 SSE 端点
    # 通过定时轮询确保前端进度不卡死，安装完成后自动跳到 100%
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            timeout=600,
            check=False,
        )
        elapsed = int(time.monotonic() - start)

        if proc.returncode == 0:
            _set_install_progress(100, "completed", "Chromium 下载完成")
            log.info(f"Chromium 下载完成，耗时 {elapsed}s")
            global _CHROMIUM_READY  # noqa: PLW0603
            _CHROMIUM_READY = None
            return True

        stderr = proc.stderr.decode("utf-8", errors="replace").strip()[:500]
        _set_install_progress(0, "failed", f"Chromium 下载失败: {stderr[:100]}")
        return False

    except subprocess.TimeoutExpired:
        _set_install_progress(0, "failed", "Chromium 下载超时")
        log.error("Chromium 下载超时（超过 10 分钟）")
        return False
    except FileNotFoundError:
        _set_install_progress(0, "failed", "无法找到 Python 可执行文件")
        log.error("无法找到 Python 可执行文件，无法安装 Chromium")
        return False
    except Exception as e:
        _set_install_progress(0, "failed", f"Chromium 下载异常: {e}")
        log.error(f"Chromium 下载异常: {e}")
        return False


async def ensure_chromium() -> bool:
    """
    确保 Chromium 浏览器可用。

    如果已可用则直接返回 True；
    否则自动下载 Chromium，下载完成后重新验证。
    安装进度可通过 get_install_progress() 获取。

    """
    if get_or_check_chromium():
        return True

    _set_install_progress(0, "starting", "准备安装...")
    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(None, _install_chromium_sync)

    if success:
        # 等待浏览器真正就绪
        import time as _time

        for _ in range(30):
            if get_or_check_chromium():
                _set_install_progress(100, "completed", "Chromium 浏览器就绪")
                return True
            _time.sleep(1)

    _set_install_progress(0, "failed", "Chromium 安装失败")
    return False


def remove_chromium() -> bool:
    """卸载 Chromium 浏览器（删除 playwright 下载的浏览器文件）"""
    global _CHROMIUM_READY  # noqa: PLW0603
    log.info("正在卸载 Chromium 浏览器...")

    # 直接手动删除浏览器缓存目录（更可靠）
    if _remove_playwright_browsers():
        _CHROMIUM_READY = False
        log.info("Chromium 浏览器已卸载")
        return True

    log.error("Chromium 卸载失败，无法删除浏览器缓存目录")
    return False


def _remove_playwright_browsers() -> bool:
    """手动删除 Playwright 浏览器缓存目录"""
    # Playwright 浏览器存储在用户目录下的特定位置
    candidates = []
    if sys.platform == "win32":
        base = Path(os.environ.get("USERPROFILE", ""))
        candidates.append(base / "AppData" / "Local" / "ms-playwright")
    elif sys.platform == "darwin":
        base = Path.home()
        candidates.append(base / "Library" / "Caches" / "ms-playwright")
    else:
        base = Path.home()
        candidates.append(base / ".cache" / "ms-playwright")

    global _CHROMIUM_READY  # noqa: PLW0603
    for cache_dir in candidates:
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir)
                log.info(f"已删除浏览器缓存: {cache_dir}")
                _CHROMIUM_READY = False
                return True
            except OSError as e:
                log.error(f"删除目录失败 {cache_dir}: {e}")

    log.warning("未找到 Playwright 浏览器缓存目录")
    return False
