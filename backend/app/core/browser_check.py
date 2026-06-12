"""
Chromium 浏览器检测与自动安装

在 PyInstaller 打包后，playwright Python 库被打进 exe，
但 Chromium 浏览器二进制 (~200MB) 不包含在安装包中。
此模块通过 ChromiumManager 类管理 Chromium 的检测、安装与卸载。

用法:
    from app.core.browser_check import chromium_manager

    ok = chromium_manager.is_ready()
    await chromium_manager.ensure()
    progress = chromium_manager.get_install_progress()
    chromium_manager.remove()
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import io
import os
import platform as _platform
import re as _re
import shutil
import subprocess
import sys
import time
import urllib.request as _request
import zipfile as _zipfile
from pathlib import Path

from app.core.log import log

# ── PyInstaller 打包钩子 ──────────────────────────────
# 模块层显式导入，强制 PyInstaller 在静态分析时追踪到这些模块，
# 确保它们被打包进 exe，否则运行时 import 会失败。
try:
    import playwright._impl._build_driver  # noqa: F401
    import playwright._impl._driver  # noqa: F401
    import playwright._impl._install  # noqa: F401
except ImportError:
    pass


class ChromiumManager:
    """Chromium 浏览器管理器——负责检测、安装、卸载和进度跟踪"""

    def __init__(self) -> None:
        # None = 未检测, True = 可用, False = 不可用
        self._ready: bool | None = None
        # 浏览器可执行文件路径（从捆绑包解压后记录，供 _check_sync 直接使用）
        self._chrome_path: str | None = None
        self._install_progress: dict[str, object] = {
            "progress": 0,
            "stage": "idle",
            "message": "",
        }

    # ── 公共 API ──────────────────────────────────────────

    @staticmethod
    def _get_browsers_dir() -> Path:
        """
        获取浏览器安装根目录。

        打包后安装在 exe 同级目录下，确保应用重启后能稳定找到。
        开发模式下使用 %LOCALAPPDATA%/ms-playwright。
        """
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            return exe_dir / "ms-playwright"
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ms-playwright"

    def is_ready(self) -> bool:
        """
        快速检查 Chromium 是否可用（使用缓存结果，不重复启动浏览器）。

        注意：仅检查缓存 + 模块导入性，不实际启动浏览器。
        需要真实检测请使用 check()。
        """
        if self._ready is not None:
            return self._ready

        try:
            import playwright  # noqa: F401
        except ImportError:
            self._ready = False
            return False

        return False

    def check(self) -> bool:
        """获取缓存状态，若未检测过则在线程中执行浏览器检测"""
        if self._ready is not None:
            return self._ready

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self._check_sync)
                self._ready = future.result(timeout=30)
        except Exception:
            self._ready = self._check_sync()

        if self._ready:
            log.info("Chromium 浏览器检测通过")
        return self._ready

    def get_install_progress(self) -> dict[str, object]:
        """获取当前安装进度"""
        return dict(self._install_progress)

    async def ensure(self) -> bool:
        """
        确保 Chromium 浏览器可用。

        如果已可用则直接返回 True；
        否则安装 Chromium（优先从捆绑包解压，否则在线下载）。
        安装进度可通过 get_install_progress() 获取。
        """
        if self.check():
            return True

        self._set_progress(0, "starting", "准备安装...")
        loop = asyncio.get_running_loop()
        success = await loop.run_in_executor(None, self._install_sync)

        if success:
            # 快速验证：给系统一点时间刷新
            for _ in range(6):
                if self.check():
                    self._set_progress(100, "completed", "Chromium 浏览器就绪")
                    return True
                time.sleep(1)

        self._set_progress(0, "failed", "Chromium 安装失败")
        return False

    def remove(self) -> bool:
        """卸载 Chromium 浏览器（删除 playwright 下载的浏览器文件）"""
        log.info("正在卸载 Chromium 浏览器...")
        if self._remove_browsers():
            self._ready = False
            log.info("Chromium 浏览器已卸载")
            return True

        log.error("Chromium 卸载失败，无法删除浏览器缓存目录")
        return False

    # ── 进度管理 ──────────────────────────────────────────

    def _set_progress(self, progress: int, stage: str, message: str) -> None:
        self._install_progress["progress"] = progress
        self._install_progress["stage"] = stage
        self._install_progress["message"] = message
        log.info(f"[install] {progress}% - {message}")

    # ── 检测 ──────────────────────────────────────────────

    def _check_sync(self) -> bool:
        """同步执行 Chromium 检测"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            log.warning("playwright 未安装")
            return False

        args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"]

        try:
            with sync_playwright() as p:
                if self._chrome_path:
                    log.info(f"使用指定路径启动 Chromium: {self._chrome_path}")
                    browser = p.chromium.launch(
                        executable_path=self._chrome_path,
                        headless=True,
                        args=args,
                    )
                else:
                    browser = p.chromium.launch(headless=True, args=args)
                browser.close()
                return True
        except Exception as e:
            log.warning(f"Chromium 启动失败: {e}")
            return False

    # ── Chromium 版本号查找 ────────────────────────────────

    def _find_revision(self) -> int | None:
        """从 playwright 捆绑数据中查找 Chromium 版本号"""
        # 方案 1: 尝试直接导入 playwright 内部模块
        try:
            from playwright._impl._build_driver import CHROMIUM_REVISION
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
        frozen = getattr(sys, "frozen", False)
        if frozen and hasattr(sys, "_MEIPASS"):
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
                m = _re.search(r"(?:chrome|chromium)_revision\s*[=:]\s*['\"]?(\d+)['\"]?", text, _re.IGNORECASE)
                if m:
                    log.info(f"从文件 {py_file.name} 获取 revision: {m.group(1)}")
                    return int(m.group(1))
            except Exception:
                pass

        log.warning("无法自动检测 revision，使用回退版本: 1140")
        return 1140

    # ── 查找捆绑包 ─────────────────────────────────────────

    def _find_bundled_chromium(self) -> Path | None:
        """查找 data/chromium/ 下的 Chromium 捆绑 zip 包"""
        search_dirs = []

        env_dir = os.environ.get("MARKFLOW_DATA_DIR")
        if env_dir:
            search_dirs.append(Path(env_dir) / "chromium")

        try:
            from config.paths import DATA_DIR  # noqa: PLC0415
            search_dirs.append(Path(DATA_DIR) / "chromium")
        except ImportError:
            pass

        frozen = getattr(sys, "frozen", False)
        if frozen:
            exe_dir = Path(sys.executable).resolve().parent
            for rel in ["data/chromium", "../data/chromium"]:
                search_dirs.append((exe_dir / rel).resolve())
        else:
            try:
                from config.paths import DATA_ROOT  # noqa: PLC0415
                search_dirs.append(DATA_ROOT / "data" / "chromium")
            except ImportError:
                pass

        for d in search_dirs:
            if not d.exists():
                continue
            for f in sorted(d.iterdir()):
                if f.suffix.lower() == ".zip" and "chromium" in f.name.lower():
                    log.info(f"找到捆绑的 Chromium 包: {f}")
                    return f
        return None

    # ── 安装 ──────────────────────────────────────────────

    def _install_sync(self) -> bool:
        """同步安装 playwright 包并下载 Chromium 浏览器（分步更新进度）"""
        self._set_progress(0, "starting", "准备安装...")
        start = time.monotonic()
        frozen = getattr(sys, "frozen", False)

        if frozen:
            self._set_progress(5, "install_package", "PyInstaller 环境，playwright 已内置")
        else:
            self._set_progress(5, "install_package", "正在安装 playwright Python 包...")
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
                    self._set_progress(0, "failed", "安装 playwright 包失败")
                    return False
            except (subprocess.TimeoutExpired, OSError) as e:
                log.error(f"安装 playwright 包异常: {e}")
                self._set_progress(0, "failed", f"安装 playwright 包异常: {e}")
                return False

        # 优先使用捆绑的 Chromium zip 包
        bundled = self._find_bundled_chromium()
        if bundled:
            self._set_progress(20, "extract_bundled", "发现捆绑的 Chromium 包，正在解压...")
            return self._install_from_bundle(start, bundled)

        self._set_progress(20, "download_chromium", "正在下载 Chromium 浏览器 (~200MB)...")

        if frozen:
            return self._install_frozen(start)

        return self._install_dev(start)

    def _install_from_bundle(self, start: float, bundle: Path) -> bool:
        """从捆绑的 zip 包解压安装 Chromium，并注册到 playwright"""
        revision = self._find_revision()
        if revision is None:
            self._set_progress(0, "failed", "无法确定 Chromium 版本号")
            return False

        browsers_path = self._get_browsers_dir()
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)
        dest_dir = browsers_path / f"chromium-{revision}"
        dest_dir.mkdir(parents=True, exist_ok=True)

        self._set_progress(40, "extracting", f"正在解压 {bundle.name}...")
        log.info(f"解压 {bundle} → {dest_dir}")

        try:
            with _zipfile.ZipFile(bundle) as zf:
                zf.extractall(dest_dir)
            elapsed = int(time.monotonic() - start)

            # 解压后尝试注册到 playwright（可选，非必需）
            try:
                from playwright._impl._install import install_browsers
                install_browsers(["chromium"], with_deps=False)
            except ImportError:
                pass  # 不依赖注册，后续会通过 executable_path 直接启动
            except Exception:
                pass

            # 验证可执行文件存在并记录路径
            chrome_candidates = [
                dest_dir / "chrome-win" / "chrome.exe",
                dest_dir / "chrome-win64" / "chrome.exe",
            ]
            chrome_exe = next((p for p in chrome_candidates if p.exists()), None)
            if chrome_exe:
                self._chrome_path = str(chrome_exe.resolve())
                log.info(f"Chromium 可执行文件: {self._chrome_path}")
                self._set_progress(100, "completed", f"Chromium 安装完成 (耗时 {elapsed}s)")
                self._ready = None
                return True

            log.error(f"解压后未找到 chrome.exe，检查目录: {dest_dir}")
            self._set_progress(0, "failed", "Chromium 解压后未找到 chrome.exe")
            return False

        except Exception as e:
            log.error(f"Chromium 解压失败: {e}")
            self._set_progress(0, "failed", f"Chromium 解压失败: {e}")
            return False

    def _install_frozen(self, start: float) -> bool:
        """PyInstaller 环境下的安装逻辑"""
        browsers_path = self._get_browsers_dir()
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)
        log.info(f"设置 PLAYWRIGHT_BROWSERS_PATH={browsers_path}")
        browsers_path.mkdir(parents=True, exist_ok=True)

        try:
            from playwright._impl._install import install_browsers
            install_browsers(["chromium"], with_deps=False)
            elapsed = int(time.monotonic() - start)
            self._set_progress(100, "completed", "Chromium 下载完成")
            log.info(f"Chromium 下载完成，耗时 {elapsed}s")
            self._ready = None
            return True
        except ImportError:
            log.warning("playwright._impl._install 不可达，尝试直接下载 Chromium")
            return self._download_direct(start, str(browsers_path))
        except Exception as e:
            log.error(f"Chromium 下载失败: {e}")
            self._set_progress(0, "failed", f"Chromium 下载失败: {e}")
            return False

    def _install_dev(self, start: float) -> bool:
        """非打包环境下的安装逻辑（通过子进程）"""
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                timeout=600,
                check=False,
            )
            elapsed = int(time.monotonic() - start)

            if proc.returncode == 0:
                self._set_progress(100, "completed", "Chromium 下载完成")
                log.info(f"Chromium 下载完成，耗时 {elapsed}s")
                self._ready = None
                return True

            stderr = proc.stderr.decode("utf-8", errors="replace").strip()
            log.error(f"Chromium 下载失败 (exit={proc.returncode}):\n{stderr[:500]}")
            self._set_progress(0, "failed", f"Chromium 下载失败: {stderr[:100]}")
            return False
        except subprocess.TimeoutExpired:
            self._set_progress(0, "failed", "Chromium 下载超时（超过 10 分钟）")
            return False
        except FileNotFoundError:
            self._set_progress(0, "failed", "无法找到 Python 可执行文件")
            return False
        except Exception as e:
            self._set_progress(0, "failed", f"Chromium 下载异常: {e}")
            return False

    def _download_direct(self, start: float, dest_parent: str) -> bool:
        """直接下载 Chromium 浏览器（备用方案）"""
        revision = self._find_revision()
        if revision is None:
            self._set_progress(0, "failed", "无法确定 Chromium 版本号")
            return False

        dest_dir = Path(dest_parent) / f"chromium-{revision}"
        self._set_progress(25, "downloading", f"正在下载 Chromium r{revision} (~200MB)...")

        chrome_paths = [
            dest_dir / "chrome-win" / "chrome.exe",
            dest_dir / "chrome-win64" / "chrome.exe",
        ]
        if dest_dir.exists() and any(p.exists() for p in chrome_paths):
            self._set_progress(100, "completed", "Chromium 已存在")
            self._ready = None
            return True

        if _platform.system() != "Windows":
            self._set_progress(0, "failed", "当前仅支持 Windows 平台下载")
            return False

        url = f"https://playwright.azureedge.net/builds/chromium/{revision}/chromium-win64.zip"
        try:
            req = _request.Request(url, headers={"User-Agent": "MarkFlow/1.0"})  # noqa: S310
            resp = _request.urlopen(req, timeout=300)  # noqa: S310
            total = int(resp.headers.get("Content-Length", 0))

            chunk_size = 8192
            downloaded = 0
            buf = io.BytesIO()
            last_pct = -1
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                buf.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = 25 + int(55 * downloaded / total)
                    if pct > last_pct:
                        mb_dl = downloaded // 1048576
                        mb_total = total // 1048576
                        self._set_progress(min(pct, 80), "downloading", f"下载中 {mb_dl}MB / {mb_total}MB")
                        last_pct = pct

            self._set_progress(80, "extracting", "正在解压 Chromium...")
            dest_dir.mkdir(parents=True, exist_ok=True)
            buf.seek(0)
            with _zipfile.ZipFile(buf) as zf:
                zf.extractall(dest_dir)

            self._set_progress(100, "completed", "Chromium 下载完成")
            self._ready = None
            return True
        except Exception as e:
            log.error(f"Chromium 直接下载失败: {e}")
            self._set_progress(0, "failed", f"Chromium 下载失败: {e}")
            return False

    # ── 卸载 ──────────────────────────────────────────────

    def _remove_browsers(self) -> bool:
        """手动删除 Playwright 浏览器缓存目录"""
        targets = [self._get_browsers_dir()]
        # 也检查用户目录下的旧位置
        if sys.platform == "win32":
            base = Path(os.environ.get("USERPROFILE", ""))
            targets.append(base / "AppData" / "Local" / "ms-playwright")
        elif sys.platform == "darwin":
            targets.append(Path.home() / "Library" / "Caches" / "ms-playwright")
        else:
            targets.append(Path.home() / ".cache" / "ms-playwright")

        for cache_dir in targets:
            if cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir)
                    log.info(f"已删除浏览器缓存: {cache_dir}")
                    self._ready = False
                    return True
                except OSError as e:
                    log.error(f"删除目录失败 {cache_dir}: {e}")

        log.warning("未找到 Playwright 浏览器缓存目录")
        return False


# ── 模块级单例 ────────────────────────────────────────────
chromium_manager = ChromiumManager()
