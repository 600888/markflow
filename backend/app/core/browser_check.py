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

# ── PyInstaller 打包钩子 ──────────────────────────────
# 模块层显式导入，强制 PyInstaller 在静态分析时追踪到这些模块，
# 确保它们被打包进 exe，否则运行时 import 会失败。
try:
    import playwright._impl._build_driver
    import playwright._impl._driver
    import playwright._impl._install  # noqa: F401
except ImportError:
    pass

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


def _is_frozen() -> bool:
    """检查是否在 PyInstaller 打包环境中运行"""
    return getattr(sys, "frozen", False)


def _find_chromium_revision() -> int | None:
    """从 playwright 捆绑数据中查找 Chromium 版本号"""
    import re as _re

    # 方案 1: 尝试直接导入 playwright 内部模块获取 revision
    try:
        from playwright._impl._build_driver import CHROMIUM_REVISION
        from playwright._impl._driver import compute_driver_executable

        if CHROMIUM_REVISION:
            log.info(f"从 playwright._impl 获取 revision: {CHROMIUM_REVISION}")
            return int(CHROMIUM_REVISION)
    except (ImportError, AttributeError):
        pass

    try:
        from playwright._impl._driver import BROWSERS

        if "chromium" in BROWSERS and "revision" in BROWSERS["chromium"]:
            rev = BROWSERS["chromium"]["revision"]
            log.info(f"从 BROWSERS 配置获取 revision: {rev}")
            return int(rev)
    except (ImportError, AttributeError, KeyError):
        pass

    # 方案 2: 搜索 Python 源文件
    py_files: list[Path] = []
    if _is_frozen() and hasattr(sys, "_MEIPASS"):
        pw_dir = Path(sys._MEIPASS) / "playwright"  # noqa: SLF001
        if pw_dir.exists():
            py_files = sorted(pw_dir.rglob("*.py"))
    else:
        try:
            import playwright as _pw

            pw_dir = Path(_pw.__file__).resolve().parent
            py_files = sorted(pw_dir.rglob("*.py"))
        except Exception:
            log.warning("无法通过 playwright 包查找 revision")

    for py_file in py_files:
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
            m = _re.search(
                r"(?:chrome|chromium)_revision\s*[=:]\s*['\"]?(\d+)['\"]?",
                text,
                _re.IGNORECASE,
            )
            if m:
                log.info(f"从文件 {py_file.name} 获取 revision: {m.group(1)}")
                return int(m.group(1))
        except Exception:
            pass

    # 方案 3: 回退到已知的稳定版本（playwright 1.40-1.48 常用的 revision）
    fallback_revision = 1140  # Chromium 131.0.6778.33 (playwright 1.48+)
    log.warning(f"无法自动检测 revision，使用回退版本: {fallback_revision}")
    return fallback_revision


def _download_chromium_direct(_start: float, dest_parent: str) -> bool:
    """直接下载 Chromium 浏览器（当 playwright._impl._install 不可用时的回退方案）"""
    global _CHROMIUM_READY  # noqa: PLW0603

    revision = _find_chromium_revision()
    if revision is None:
        _set_install_progress(0, "failed", "无法确定 Chromium 版本号，请查看日志")
        log.error("无法从 playwright 捆绑数据中获取 Chromium revision")
        return False

    dest_dir = Path(dest_parent) / f"chromium-{revision}"
    _set_install_progress(25, "downloading", f"正在下载 Chromium r{revision} (~200MB)...")
    log.info(f"目标目录: {dest_dir}")

    # 检查是否已存在（支持多种路径格式）
    chrome_paths = [
        dest_dir / "chrome-win" / "chrome.exe",
        dest_dir / "chrome-win64" / "chrome.exe",
    ]
    if dest_dir.exists() and any(p.exists() for p in chrome_paths):
        log.info("Chromium 已存在，跳过下载")
        _set_install_progress(100, "completed", "Chromium 已存在")
        _CHROMIUM_READY = None  # 强制重新检测
        return True

    import io

    # Chromium 下载 URL（playwright 官方 CDN）
    import platform as _platform
    import urllib.request as _request
    import zipfile as _zipfile

    if _platform.system() != "Windows":
        _set_install_progress(0, "failed", "当前仅支持 Windows 平台下载")
        return False

    url = f"https://playwright.azureedge.net/builds/chromium/{revision}/chromium-win64.zip"
    log.info(f"下载 URL: {url}")

    try:
        # 流式下载，避免内存占用过大
        req = _request.Request(url, headers={"User-Agent": "MarkFlow/1.0"})  # noqa: S310
        resp = _request.urlopen(req, timeout=300)  # noqa: S310
        total = int(resp.headers.get("Content-Length", 0))

        chunk_size = 8192
        downloaded = 0
        buf = io.BytesIO()
        last_reported_pct = -1
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            buf.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = 25 + int(55 * downloaded / total)
                if pct > last_reported_pct:
                    mb_dl = downloaded // 1048576
                    mb_total = total // 1048576
                    _set_install_progress(
                        min(pct, 80),
                        "downloading",
                        f"下载中 {mb_dl}MB / {mb_total}MB",
                    )
                    last_reported_pct = pct

        _set_install_progress(80, "extracting", "正在解压 Chromium...")
        log.info(f"下载完成 ({downloaded} bytes)，正在解压...")

        # 解压到目标目录
        dest_dir.mkdir(parents=True, exist_ok=True)
        buf.seek(0)
        with _zipfile.ZipFile(buf) as zf:
            zf.extractall(dest_dir)

        log.info(f"解压完成: {dest_dir}")
        _set_install_progress(100, "completed", "Chromium 下载完成")
        _CHROMIUM_READY = None
        return True

    except Exception as e:
        log.error(f"Chromium 直接下载失败: {e}")
        _set_install_progress(0, "failed", f"Chromium 下载失败: {e}")
        return False


def _install_chromium_sync() -> bool:
    """同步安装 playwright 包并下载 Chromium 浏览器（分步更新进度）"""
    global _CHROMIUM_READY  # noqa: PLW0603
    _set_install_progress(0, "starting", "准备安装...")
    start = time.monotonic()

    is_frozen = _is_frozen()

    if is_frozen:
        # PyInstaller 打包环境：playwright 已打包在 exe 中，跳过 pip install
        _set_install_progress(5, "install_package", "PyInstaller 环境，playwright 已内置")
    else:
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
                log.error(f"安装 playwright 包失败 (exit={result.returncode}): {stderr}")
                _set_install_progress(0, "failed", "安装 playwright 包失败")
                return False
        except (subprocess.TimeoutExpired, OSError) as e:
            log.error(f"安装 playwright 包异常: {e}")
            _set_install_progress(0, "failed", f"安装 playwright 包异常: {e}")
            return False

    _set_install_progress(20, "download_chromium", "正在下载 Chromium 浏览器 (~200MB)...")

    if is_frozen:
        # ── PyInstaller 环境下：同进程直接调用 playwright 内部安装函数 ──
        # 不走子进程（避免编码乱码、模块路径不一致等问题）
        browsers_path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ms-playwright"
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)
        log.info(f"设置 PLAYWRIGHT_BROWSERS_PATH={browsers_path}")
        browsers_path.mkdir(parents=True, exist_ok=True)

        try:
            from playwright._impl._install import install_browsers

            install_browsers(["chromium"], with_deps=False)
            elapsed = int(time.monotonic() - start)
            _set_install_progress(100, "completed", "Chromium 下载完成")
            log.info(f"Chromium 下载完成，耗时 {elapsed}s")
            _CHROMIUM_READY = None
            return True
        except ImportError:
            # playwright._impl._install 未打包进 exe，尝试直接下载
            log.warning("playwright._impl._install 不可达，尝试直接下载 Chromium")
            return _download_chromium_direct(start, str(browsers_path))
        except Exception as e:
            log.error(f"Chromium 下载失败: {e}")
            _set_install_progress(0, "failed", f"Chromium 下载失败: {e}")
            return False

    # ── 非打包环境：通过子进程下载 ──
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
            _CHROMIUM_READY = None
            return True

        stderr_text = proc.stderr.decode("utf-8", errors="replace").strip()
        log.error(f"Chromium 下载失败 (exit={proc.returncode}):\n{stderr_text[:500]}")
        _set_install_progress(0, "failed", f"Chromium 下载失败: {stderr_text[:100]}")
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
