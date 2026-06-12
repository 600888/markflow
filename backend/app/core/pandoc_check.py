"""
Pandoc 检测与自动安装

在 PyInstaller 打包后，pypandoc Python 库被打进 exe，
但 Pandoc 系统级二进制不包含在安装包中。
此模块通过 PandocManager 类管理 Pandoc 的检测、安装与卸载。

捆绑的安装包位于 data/ 目录下，由 PyInstaller 打包机制或 Tauri 资源分发。

用法:
    from app.core.pandoc_check import pandoc_manager

    ok = pandoc_manager.is_installed()
    info = pandoc_manager.get_info()
    success = await pandoc_manager.ensure()
    progress = pandoc_manager.get_install_progress()
"""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from app.core.log import log


class PandocManager:
    """Pandoc 安装管理器——负责检测、安装、卸载和进度跟踪"""

    def __init__(self) -> None:
        # None = 未检测, True = 可用, False = 不可用
        self._ready: bool | None = None
        self._version: str | None = None
        self._install_progress: dict[str, object] = {
            "progress": 0,
            "stage": "idle",
            "message": "",
        }
        # 持久化状态文件路径（%APPDATA%/MarkFlow/.pandoc_status）
        self._status_file: Path | None = None
        self._init_status_file()
        # 启动时尝试从持久化文件恢复状态
        self._load_status()

    # ── 持久化状态 ──────────────────────────────────────────

    def _init_status_file(self) -> None:
        """初始化持久化状态文件路径"""
        appdata = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or ""
        if appdata:
            markflow_dir = Path(appdata) / "MarkFlow"
            try:
                markflow_dir.mkdir(parents=True, exist_ok=True)
                self._status_file = markflow_dir / ".pandoc_status"
            except OSError:
                pass

    def _save_status(self) -> None:
        """将安装状态持久化到文件（重启后恢复用）"""
        if self._status_file is None:
            return
        try:
            self._status_file.write_text(
                f"version={self._version or 'unknown'}\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    def _load_status(self) -> None:
        """从持久化文件恢复安装状态"""
        if self._status_file is None or not self._status_file.exists():
            return
        try:
            text = self._status_file.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("version="):
                    self._version = line[len("version="):].strip()
                    break
            # 只要文件存在，说明之前安装成功过
            self._ready = True
            log.info(f"从持久化状态恢复: Pandoc 已安装, 版本: {self._version}")
        except OSError:
            pass

    def _clear_status(self) -> None:
        """删除持久化状态文件（卸载后调用）"""
        if self._status_file and self._status_file.exists():
            try:
                self._status_file.unlink()
            except OSError:
                pass

    # ── 公共 API ──────────────────────────────────────────

    def is_installed(self, force: bool = False) -> bool:
        """
        检查 Pandoc 是否可用。

        仅缓存 True（已安装）的结果，False 结果不会缓存。
        这样用户手动安装 Pandoc 后，下次查询会自动重新检测。

        Args:
            force: 为 True 时绕过缓存，强制真实检测。卸载后验证请用 force=True。
        """
        if not force and self._ready is True:
            return True

        ok, _ = self._check_sync()
        self._ready = ok
        return ok

    def get_info(self) -> dict[str, object]:
        """获取 Pandoc 的详细状态信息"""
        available = self.is_installed()
        version = self._version
        installer = self._find_installer()

        return {
            "available": available,
            "version": version or "",
            "installer_found": installer is not None,
            "installer_path": str(installer) if installer else "",
        }

    def get_install_progress(self) -> dict[str, object]:
        """获取当前安装进度"""
        return dict(self._install_progress)

    async def ensure(self) -> bool:
        """确保 Pandoc 可用，否则从捆绑的 MSI 安装"""
        if self.is_installed():
            self._set_progress(100, "completed", "Pandoc 已就绪")
            return True

        self._set_progress(0, "starting", "准备安装 Pandoc...")
        loop = asyncio.get_running_loop()
        success = await loop.run_in_executor(None, self._install_sync)

        if success:
            self._set_progress(100, "completed", "Pandoc 安装完成")
            return True

        self._set_progress(0, "failed", "Pandoc 安装失败")
        return False

    def remove(self) -> bool:
        """卸载 Pandoc"""
        self._set_progress(0, "starting", "准备卸载 Pandoc...")
        return self._remove_sync()

    # ── 进度管理 ──────────────────────────────────────────

    def _set_progress(self, progress: int, stage: str, message: str) -> None:
        self._install_progress["progress"] = progress
        self._install_progress["stage"] = stage
        self._install_progress["message"] = message
        log.info(f"[pandoc-install] {progress}% - {message}")

    # ── 缓存管理 ─────────────────────────────────────────

    @staticmethod
    def _clear_pypandoc_cache() -> None:
        """
        清除 pypandoc 内部路径缓存。

        pypandoc.get_pandoc_path() 在首次找到 pandoc 后会缓存路径，
        不清理的话即使 pandoc 已被卸载，get_pandoc_path() 仍返回旧路径。
        """
        try:
            import pypandoc  # noqa: PLC0415
            pypandoc._pandoc_path = None  # type: ignore[attr-defined]
        except (ImportError, AttributeError):
            pass

    # ── 检测 ──────────────────────────────────────────────

    def _check_sync(self) -> tuple[bool, str]:
        """同步检测 Pandoc 是否可用（首次启动或 force 时调用）"""
        # 方案 1: 直接运行 pandoc --version
        try:
            result = subprocess.run(
                ["pandoc", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                first_line = result.stdout.splitlines()[0] if result.stdout else ""
                m = re.search(r"(\d+\.\d+(?:\.\d+)?)", first_line)
                self._version = m.group(1) if m else "unknown"
                self._save_status()
                log.info(f"Pandoc 可用, 版本: {self._version}")
                return True, self._version
        except (subprocess.TimeoutExpired, OSError):
            pass

        # 方案 2: 标准安装路径 + 用户级安装路径
        user_local = os.environ.get("LOCALAPPDATA", "")
        user_roaming = os.environ.get("APPDATA", "")
        search_paths = [
            Path("C:/Program Files/Pandoc/pandoc.exe"),
            Path("C:/Program Files (x86)/Pandoc/pandoc.exe"),
        ]
        if user_local:
            search_paths.append(Path(user_local) / "Pandoc" / "pandoc.exe")
        if user_roaming:
            search_paths.append(Path(user_roaming) / "Pandoc" / "pandoc.exe")
        for path in search_paths:
            if path.exists():
                result = subprocess.run(
                    [str(path), "--version"],
                    capture_output=True, text=True, timeout=10, check=False,
                )
                if result.returncode == 0:
                    first_line = result.stdout.splitlines()[0] if result.stdout else ""
                    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", first_line)
                    self._version = m.group(1) if m else "unknown"
                    self._save_status()
                    log.info(f"Pandoc 可用 (标准路径: {path}), 版本: {self._version}")
                    return True, self._version

        # 方案 3: pypandoc 搜索
        try:
            import pypandoc  # noqa: PLC0415
            pypandoc_path = pypandoc.get_pandoc_path()
            result = subprocess.run(
                [pypandoc_path, "--version"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if result.returncode == 0:
                first_line = result.stdout.splitlines()[0] if result.stdout else ""
                m = re.search(r"(\d+\.\d+(?:\.\d+)?)", first_line)
                self._version = m.group(1) if m else "unknown"
                self._save_status()
                log.info(f"Pandoc 可用 (pypandoc), 版本: {self._version}")
                return True, self._version
        except (ImportError, OSError):
            pass

        log.warning("Pandoc 未找到（PATH / 标准路径 / pypandoc 均不可用）")
        return False, ""

    # ── 查找安装包 ────────────────────────────────────────

    def _find_installer(self) -> Path | None:
        """查找捆绑的 Pandoc MSI 安装包路径"""
        env_dir = os.environ.get("MARKFLOW_DATA_DIR")
        if env_dir:
            msi = self._find_msi(Path(env_dir))
            if msi:
                log.info(f"从 MARKFLOW_DATA_DIR 找到 Pandoc 安装包: {msi}")
                return msi

        try:
            from config.paths import DATA_DIR  # noqa: PLC0415

            msi = self._find_msi(Path(DATA_DIR))
            if msi:
                log.info(f"从 DATA_DIR 找到 Pandoc 安装包: {msi}")
                return msi
        except ImportError:
            pass

        frozen = getattr(sys, "frozen", False)
        if frozen:
            exe_dir = Path(sys.executable).resolve().parent
            for rel in ["data", "../data"]:
                msi = self._find_msi((exe_dir / rel).resolve())
                if msi:
                    log.info(f"从 exe 相对路径找到 Pandoc 安装包: {msi}")
                    return msi
        else:
            try:
                from config.paths import DATA_ROOT  # noqa: PLC0415

                msi = self._find_msi(DATA_ROOT / "data")
                if msi:
                    log.info(f"从项目 data/ 找到 Pandoc 安装包: {msi}")
                    return msi
            except ImportError:
                pass

        log.warning("未找到 Pandoc 安装包")
        return None

    @staticmethod
    def _find_msi(directory: Path) -> Path | None:
        """在目录中查找 pandoc MSI 文件"""
        if not directory.exists():
            return None
        for f in sorted(directory.iterdir()):
            if f.suffix.lower() == ".msi" and "pandoc" in f.name.lower():
                return f
        return None

    # ── 注册表操作 ────────────────────────────────────────

    @staticmethod
    def _get_uninstall_cmd() -> str | None:
        """
        从 Windows 注册表查找 Pandoc 的卸载命令。

        返回完整 msiexec 命令字符串（如 'MsiExec.exe /X{...}'），
        调用方直接执行即可。

        搜索优先级:
        1. QuietUninstallString（微软官方推荐的静默卸载命令）
        2. UninstallString + 提取 ProductCode（最准确的来源）
        3. 子键名本身（如果就是 GUID 格式）
        """
        import winreg  # noqa: PLC0415

        keys = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]
        for key_path in keys:
            i = 0
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ) as key:
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            i += 1
                        except OSError:
                            break

                        try:
                            with winreg.OpenKey(
                                winreg.HKEY_LOCAL_MACHINE, f"{key_path}\\{subkey_name}", 0, winreg.KEY_READ
                            ) as subkey:
                                try:
                                    name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                    if "pandoc" not in name.lower():
                                        continue
                                except OSError:
                                    continue

                                # 方案 1: QuietUninstallString — 微软推荐的静默卸载命令
                                # 改为直接返回交互式 uninstall（去除 /quiet）
                                try:
                                    qus = winreg.QueryValueEx(subkey, "QuietUninstallString")[0]
                                    if qus.strip():
                                        interactive = re.sub(r"\s*/quiet\b", "", qus, flags=re.IGNORECASE).strip()
                                        return interactive
                                except OSError:
                                    pass

                                # 方案 2: UninstallString — 提取其中的 ProductCode
                                try:
                                    us = winreg.QueryValueEx(subkey, "UninstallString")[0]
                                    m = re.search(r"\{([A-F0-9-]+)\}", us)
                                    if m:
                                        return f'msiexec /x {{{m.group(1)}}}'
                                except OSError:
                                    pass

                                # 方案 3: 子键名本身
                                if subkey_name.startswith("{"):
                                    return f"msiexec /x {subkey_name}"
                        except OSError:
                            continue
            except OSError:
                continue
        return None

    # ── 安装 ──────────────────────────────────────────────

    def _install_sync(self) -> bool:
        """从捆绑的 MSI 同步安装 Pandoc"""
        if self.is_installed():
            self._set_progress(100, "completed", "Pandoc 已安装")
            return True

        installer = self._find_installer()
        if not installer:
            self._set_progress(0, "failed", "未找到 Pandoc 安装包")
            log.error("未找到 Pandoc MSI 安装包，请先将 MSI 放入 data/ 目录")
            return False

        self._set_progress(10, "starting", f"准备安装 Pandoc ({installer.name})...")
        log.info(f"安装包: {installer} ({installer.stat().st_size / 1024 / 1024:.1f} MB)")

        start = time.monotonic()
        log_dir = Path(os.environ.get("TEMP", ".")) / "markflow-pandoc-install"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "pandoc-install.log"

        # 交互式安装：弹出标准 Windows Installer 向导，用户确认后安装
        cmd = f'msiexec /i "{installer.resolve()}" /log "{log_file}"'
        self._set_progress(30, "installing", "正在打开 Pandoc 安装向导，请按提示完成安装...")

        try:
            result = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=300, check=False)
            elapsed = int(time.monotonic() - start)
            log.info(f"msiexec 返回码: {result.returncode}, 耗时: {elapsed}s")

            if result.returncode in (0, 1641, 3010):
                total = int(time.monotonic() - start)
                # msiexec 返回成功，实际验证 Pandoc 是否可用
                self._clear_pypandoc_cache()
                ok, ver = self._check_sync()
                if ok:
                    self._ready = True
                    self._save_status()
                    self._set_progress(100, "completed", f"Pandoc 安装完成 (版本 {ver}, 耗时 {total}s)")
                    return True
                # msiexec 成功但检测不到——可能安装到了非标准路径，用文件名版本号标记
                log.warning("msiexec 返回成功但 _check_sync 未检测到 Pandoc，使用文件名版本号")
                ver_match = re.search(r"pandoc[_-](\d+\.\d+(?:\.\d+)*)", installer.name, re.IGNORECASE)
                self._version = ver_match.group(1) if ver_match else None
                self._ready = True
                self._save_status()
                self._set_progress(100, "completed", f"Pandoc 安装完成 (耗时 {total}s)")
                return True

            error_msg = self._read_install_error(result.returncode, result.stdout, result.stderr, log_file)
            self._set_progress(0, "failed", f"Pandoc 安装失败: {error_msg}")
            return False

        except subprocess.TimeoutExpired:
            self._set_progress(0, "failed", "Pandoc 安装超时（超过 2 分钟）")
            return False
        except FileNotFoundError:
            self._set_progress(0, "failed", "未找到 msiexec.exe，系统可能不支持 MSI 安装")
            return False
        except Exception as e:
            self._set_progress(0, "failed", f"Pandoc 安装异常: {e}")
            log.error(f"Pandoc 安装异常: {e}")
            return False

    @staticmethod
    def _read_install_error(returncode: int, stdout: str, stderr: str, log_file: Path) -> str:
        """从安装日志中提取错误信息"""
        msg = (stdout or "") + (stderr or "")
        if msg.strip():
            return msg[:300]
        if log_file.exists():
            content = log_file.read_text(encoding="utf-8", errors="replace")
            for line in content.splitlines():
                if "Error" in line or "error" in line or "returned" in line:
                    return line[:200]
        return f"msiexec 返回码 {returncode}"

    # ── 卸载 ──────────────────────────────────────────────

    def _remove_sync(self) -> bool:
        """同步卸载 Pandoc"""
        if not self.is_installed():
            self._set_progress(100, "completed", "Pandoc 未安装")
            return True

        self._set_progress(10, "uninstalling", "正在查找 Pandoc 产品信息...")
        log.info("正在卸载 Pandoc...")

        uninstall_cmd = self._get_uninstall_cmd()
        if uninstall_cmd:
            return self._uninstall_via_cmd(uninstall_cmd)

        log.warning("未在注册表中找到 Pandoc 产品信息，尝试直接删除文件")
        return self._uninstall_via_files()

    def _uninstall_via_cmd(self, cmd: str) -> bool:
        """交互式卸载 Pandoc（弹出 Windows Installer 卸载确认框）"""
        m = re.search(r"\{([A-F0-9-]+)\}", cmd, re.IGNORECASE)
        code_display = m.group(0) if m else cmd[:60]
        log.info(f"执行卸载命令: {cmd}")

        self._set_progress(40, "uninstalling", f"正在打开 Pandoc 卸载向导 ({code_display})...")

        try:
            result = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )

            if result.returncode in (0, 1641, 3010):
                # msiexec 返回成功即信任，不再验证
                # 用户本地可能还有另一份 pandoc 备份，不影响 MSI 卸载结果的判断
                self._clear_pypandoc_cache()
                self._ready = False
                self._version = None
                self._clear_status()  # 清除持久化状态
                self._set_progress(100, "completed", "Pandoc 已卸载")
                return True

            self._set_progress(0, "failed", f"卸载失败 (exit={result.returncode})")
            return False

        except subprocess.TimeoutExpired:
            self._set_progress(0, "failed", "Pandoc 卸载超时")
            return False
        except Exception as e:
            self._set_progress(0, "failed", f"Pandoc 卸载异常: {e}")
            return False

    def _uninstall_via_files(self) -> bool:
        """直接删除 Pandoc 文件（备用方案）"""
        self._set_progress(40, "uninstalling", "尝试直接删除 Pandoc 文件...")
        try:
            import pypandoc  # noqa: PLC0415

            pandoc_path = Path(pypandoc.get_pandoc_path())
            pandoc_dir = pandoc_path.parent
            if pandoc_dir.exists() and "pandoc" in pandoc_dir.name.lower():
                shutil.rmtree(pandoc_dir)
                self._ready = None
                self._version = None
                time.sleep(1)
                if not self.is_installed():
                    self._set_progress(100, "completed", "Pandoc 已卸载")
                    return True
        except Exception as e:
            log.error(f"直接删除 Pandoc 文件失败: {e}")

        self._set_progress(0, "failed", "Pandoc 卸载失败，请手动卸载")
        return False


# ── 模块级单例 ────────────────────────────────────────────
pandoc_manager = PandocManager()
