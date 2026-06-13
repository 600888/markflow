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

        # 确保 PLAYWRIGHT_BROWSERS_PATH 已设置，让 Playwright 能发现安装的浏览器
        browsers_path = self._get_browsers_dir()
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browsers_path))

        # 如果 _chrome_path 为空，自动在浏览器目录中扫描已安装的可执行文件
        # 解决应用重启后 _chrome_path 丢失的问题
        if not self._chrome_path:
            chrome_exe = self._find_chrome_in_browsers_dir(browsers_path)
            if chrome_exe:
                self._chrome_path = chrome_exe
                log.info(f"自动发现已安装的 Chromium: {self._chrome_path}")

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
        """从 playwright 捆绑数据或已安装的浏览器中查找 Chromium 版本号"""
        # 方案 0: 从已存在的浏览器安装目录中读取版本号（最可靠）
        browsers_dir = self._get_browsers_dir()
        if browsers_dir.exists():
            for d in sorted(browsers_dir.iterdir(), reverse=True):
                if d.is_dir():
                    m = _re.search(r"(?:chromium|chrome)[_-](\d+)$", d.name, _re.IGNORECASE)
                    if m:
                        rev = int(m.group(1))
                        log.info(f"从已存在的浏览器目录获取 revision: {rev} ({d.name})")
                        return rev

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

        # 方案 2: 搜索 Python 源文件（支持新版 Playwright 的多种命名格式）
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

        # 匹配多种可能的 revision 定义格式
        revision_patterns = [
            _re.compile(r'(?:chrome|chromium)_revision\s*[=:]\s*[\'"]?(\d+)[\'"]?', _re.IGNORECASE),
            _re.compile(r'revision\s*[:=]\s*(\d+)\s*[,}\n]', _re.IGNORECASE),
            _re.compile(r'["\']chromium["\'].*?["\']revision["\']\s*[:=]\s*(\d+)', _re.IGNORECASE | _re.DOTALL),
            _re.compile(r'BROWSERS\s*=\s*\{.*?chromium.*?revision.*?(\d+)', _re.IGNORECASE | _re.DOTALL),
        ]

        for py_file in py_files:
            try:
                text = py_file.read_text(encoding="utf-8", errors="replace")
                for pattern in revision_patterns:
                    m = pattern.search(text)
                    if m:
                        log.info(f"从文件 {py_file.name} 获取 revision: {m.group(1)}")
                        return int(m.group(1))
            except Exception:
                pass

        # 方案 3: 尝试解析 playwright 的 driver 数据文件
        try:
            import json as _json
            if frozen and hasattr(sys, "_MEIPASS"):
                data_files = list(Path(sys._MEIPASS).rglob("**/browsers.json"))  # noqa: SLF001
                for df in data_files:
                    try:
                        data = _json.loads(df.read_text(encoding="utf-8"))
                        if "chromium" in data and "revision" in data["chromium"]:
                            rev = data["chromium"]["revision"]
                            log.info(f"从 browsers.json 获取 revision: {rev}")
                            return int(rev)
                    except Exception:
                        pass
        except Exception:
            pass

        # 方案 4: 尝试读取 playwright 内置的 driver 源文件中的浏览器定义
        try:
            from playwright._impl._driver import _DRIVER_PATH  # type: ignore[attr-defined]
            match = _re.search(rb'revision["\']?\s*[:=]\s*(\d+)', open(_DRIVER_PATH, 'rb').read())  # noqa: SIM115, PTH123
            if match:
                log.info(f"从 _DRIVER_PATH 获取 revision: {match.group(1).decode()}")
                return int(match.group(1).decode())
        except Exception:
            pass

        log.warning("无法自动检测 revision，使用回退版本: 1140")
        return 1140

    # ── 查找捆绑包 ─────────────────────────────────────────

    def _find_bundled_chromium(self) -> Path | None:
        """查找 data/chromium/ 下的 Chromium 捆绑 zip 包

        搜索策略（frozen 模式下）:
        1. MARKFLOW_DATA_DIR/chromium/（Tauri env var）
        2. config.paths.DATA_DIR/chromium/（PyInstaller 打包目录）
        3. exe 所在目录及其所有祖先目录的 data/chromium/（适配各种安装布局）
        4. sys._MEIPASS/data/chromium/（PyInstaller internal temp dir）
        """
        search_dirs: list[Path] = []

        # 1. MARKFLOW_DATA_DIR 环境变量（Tauri/外部传入）
        env_dir = os.environ.get("MARKFLOW_DATA_DIR")
        if env_dir:
            search_dirs.append(Path(env_dir) / "chromium")

        # 2. config.paths.DATA_DIR（PyInstaller 内嵌或开发模式配置）
        try:
            from config.paths import DATA_DIR  # noqa: PLC0415
            search_dirs.append(Path(DATA_DIR) / "chromium")
        except ImportError:
            pass

        frozen = getattr(sys, "frozen", False)

        # 3. 从 exe 所在目录向上遍历各级祖先目录的 data/chromium/
        #    适配 Tauri 资源可能被解压到的各种位置
        if frozen:
            exe_dir = Path(sys.executable).resolve().parent
            # 先从最近的上三级目录搜索（最常出现的位置）
            for level in range(3):
                candidate = exe_dir
                for _ in range(level):
                    candidate = candidate.parent
                search_dirs.append(candidate / "data" / "chromium")

            # 再往上一路搜到根目录（兜底）
            parent = exe_dir.parent
            while parent != parent.parent:  # 直到根目录
                candidate = parent / "data" / "chromium"
                if candidate not in search_dirs:
                    search_dirs.append(candidate)
                parent = parent.parent

            # 4. PyInstaller internal temp 目录
            try:
                meipass = Path(sys._MEIPASS) / "data" / "chromium"  # noqa: SLF001
                if meipass not in search_dirs:
                    search_dirs.append(meipass)
            except AttributeError:
                pass
        else:
            # 开发模式
            try:
                from config.paths import DATA_ROOT  # noqa: PLC0415
                search_dirs.append(DATA_ROOT / "data" / "chromium")
            except ImportError:
                pass
            # 也搜工作目录
            search_dirs.append(Path.cwd() / "data" / "chromium")

        # 过滤不存在的目录并搜索 zip
        found_paths: list[str] = []
        for d in search_dirs:
            if not d.exists():
                found_paths.append(f"{d} (不存在)")
                continue
            for f in sorted(d.iterdir()):
                if f.suffix.lower() == ".zip" and "chromium" in f.name.lower():
                    log.info(f"找到捆绑的 Chromium 包: {f}")
                    return f
            found_paths.append(f"{d} (无 zip 文件)")

        log.debug(f"未找到 Chromium 捆绑包，已搜索: {', '.join(found_paths)}")
        return None

    @staticmethod
    def _get_browser_dirname(revision: int) -> str:
        """获取 Playwright 期望的浏览器目录名（如 chromium-1140 或 chromium_headless_shell-1223）"""
        try:
            from playwright._impl._driver import BROWSERS  # type: ignore[attr-defined]
            browser_name = BROWSERS.get("chromium", {}).get("name", "chromium")
            return f"{browser_name}-{revision}"
        except (ImportError, AttributeError, KeyError):
            # 回退：检测 headless_shell 命名格式
            if revision >= 1200:
                return f"chromium_headless_shell-{revision}"
            return f"chromium-{revision}"

    @staticmethod
    def _get_chrome_candidates(dest_dir: Path) -> list[Path]:
        """获取可能的 Chrome/Chromium 可执行文件路径列表（兼容新旧版本）"""
        return [
            dest_dir / "chrome-win64" / "chrome.exe",
            dest_dir / "chrome-win" / "chrome.exe",
            dest_dir / "chrome-headless-shell-win64" / "chrome-headless-shell.exe",
            dest_dir / "chrome-headless-shell-win" / "chrome-headless-shell.exe",
        ]

    @staticmethod
    def _find_chrome_in_browsers_dir(browsers_dir: Path) -> str | None:
        """在浏览器根目录下扫描所有子目录，查找 chrome/chrome-headless-shell 可执行文件"""
        if not browsers_dir.exists():
            return None
        for sub in sorted(browsers_dir.iterdir()):
            if not sub.is_dir():
                continue
            for exe in ChromiumManager._get_chrome_candidates(sub):
                if exe.exists():
                    resolved = str(exe.resolve())
                    log.info(f"在浏览器目录中发现可执行文件: {resolved}")
                    return resolved
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
        dirname = self._get_browser_dirname(revision)
        dest_dir = browsers_path / dirname
        dest_dir.mkdir(parents=True, exist_ok=True)

        self._set_progress(40, "extracting", f"正在解压 {bundle.name}...")
        log.info(f"解压 {bundle} → {dest_dir}")

        try:
            with _zipfile.ZipFile(bundle) as zf:
                zf.extractall(dest_dir)
            elapsed = int(time.monotonic() - start)

            # 验证可执行文件存在并记录路径
            chrome_candidates = self._get_chrome_candidates(dest_dir)
            chrome_exe = next((p for p in chrome_candidates if p.exists()), None)

            # 如果预期路径没有找到，扫描整个 browsers 目录（兼容目录名不匹配的情况）
            if not chrome_exe:
                chrome_exe_path = self._find_chrome_in_browsers_dir(browsers_path)
                if chrome_exe_path:
                    self._chrome_path = chrome_exe_path
                    log.info(f"通过扫描找到 Chromium 可执行文件: {self._chrome_path}")
                    chrome_exe = True  # 标记为找到

            if chrome_exe:
                if not self._chrome_path:
                    self._chrome_path = str(chrome_exe.resolve())
                    log.info(f"Chromium 可执行文件: {self._chrome_path}")

                # 解压后尝试注册到 playwright（可选，非必需）
                try:
                    from playwright._impl._install import install_browsers
                    install_browsers(["chromium"], with_deps=False)
                except ImportError:
                    pass
                except Exception:
                    pass

                self._set_progress(100, "completed", f"Chromium 安装完成 (耗时 {elapsed}s)")
                self._ready = None
                return True

            log.error(f"解压后未找到 chrome.exe 或 chrome-headless-shell.exe，检查目录: {dest_dir}")
            self._set_progress(0, "failed", "Chromium 解压后未找到可执行文件")
            return False

        except Exception as e:
            log.error(f"Chromium 解压失败: {e}")
            self._set_progress(0, "failed", f"Chromium 解压失败: {e}")
            return False

    def _install_frozen(self, start: float) -> bool:
        """PyInstaller 环境下的安装逻辑（先尝试 Playwright 内置安装器，失败后降级到直接下载）"""
        browsers_path = self._get_browsers_dir()
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)
        log.info(f"设置 PLAYWRIGHT_BROWSERS_PATH={browsers_path}")
        browsers_path.mkdir(parents=True, exist_ok=True)

        # 先试试 Playwright 内置的 install_browsers
        try:
            from playwright._impl._install import install_browsers
            install_browsers(["chromium"], with_deps=False)
            elapsed = int(time.monotonic() - start)
            log.info(f"playwright 内置 install_browsers 完成，耗时 {elapsed}s")

            # 扫描浏览器目录，记录可执行文件路径
            chrome_path = self._find_chrome_in_browsers_dir(browsers_path)
            if chrome_path:
                self._chrome_path = chrome_path
                log.info(f"已记录 Chromium 路径: {self._chrome_path}")
                self._set_progress(100, "completed", "Chromium 下载完成")
                self._ready = None
                return True

            log.warning("install_browsers 成功但未找到可执行文件")
        except ImportError:
            log.warning("playwright._impl._install 不可达")
        except Exception as e:
            log.warning(f"playwright 内置安装器失败，将降级到直接下载: {e}")

        # 降级到直接下载（不依赖 Playwright 内部安装器）
        log.info("降级到直接下载 Chromium...")
        self._set_progress(25, "downloading", "正在直接下载 Chromium (~200MB)...")
        return self._download_direct(start, str(browsers_path))

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

        dirname = self._get_browser_dirname(revision)
        dest_dir = Path(dest_parent) / dirname
        self._set_progress(25, "downloading", f"正在下载 Chromium r{revision} (~200MB)...")

        chrome_paths = self._get_chrome_candidates(dest_dir)
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

            # 扫描浏览器目录自动发现可执行文件（兼容新旧命名格式）
            browsers_path = Path(dest_parent)
            chrome_path = self._find_chrome_in_browsers_dir(browsers_path)
            if chrome_path:
                self._chrome_path = chrome_path
                log.info(f"已记录 Chromium 路径: {self._chrome_path}")

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
