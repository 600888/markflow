"""LibreOffice discovery and managed installation."""

# ruff: noqa: D102, TRY301

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

from app.utils.config import AppSettings


class LibreOfficeManager:
    """Locate LibreOffice and manage MarkFlow's private Windows copy."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        self._executable: Path | None = None
        self._version = ""
        self._expected_sha256 = ""
        self._progress: dict[str, object] = {"progress": 0, "message": "等待安装"}
        self._install_lock = threading.Lock()

    @property
    def managed_root(self) -> Path:
        return self.settings.data_dir / "modules" / "libreoffice"

    @property
    def cache_dir(self) -> Path:
        return self.settings.data_dir / "module-cache" / "libreoffice"

    @property
    def installer_name(self) -> str:
        return Path(self.settings.libreoffice_download_url).name

    def find_executable(self, *, refresh: bool = False) -> Path | None:
        if self._executable is not None and not refresh and self._executable.is_file():
            return self._executable
        for candidate in self._candidates():
            if candidate.is_file():
                self._executable = candidate.resolve()
                return self._executable
        self._executable = None
        self._version = ""
        return None

    def is_available(self, *, refresh: bool = False) -> bool:
        executable = self.find_executable(refresh=refresh)
        return executable is not None and bool(self.get_version(refresh=refresh))

    def is_managed(self, executable: Path | None = None) -> bool:
        executable = executable or self.find_executable()
        if executable is None:
            return False
        try:
            executable.resolve().relative_to(self.managed_root.resolve())
            return True
        except ValueError:
            return False

    def get_version(self, *, refresh: bool = False) -> str:
        executable = self.find_executable(refresh=refresh)
        if executable is None:
            return ""
        if self._version and not refresh:
            return self._version
        try:
            completed = subprocess.run(
                [str(executable), "--version"], check=False, capture_output=True, timeout=8
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        output = (completed.stdout + completed.stderr).decode(errors="replace").strip()
        if completed.returncode != 0 or not output:
            return ""
        match = re.search(r"\d+(?:\.\d+){1,3}", output)
        self._version = match.group(0) if match else output[:64]
        return self._version

    def find_installer(self) -> Path | None:
        candidates = [self.cache_dir / self.installer_name]
        roots = [self.settings.data_dir, Path(sys.executable).resolve().parent]
        for root in roots:
            candidates.extend(root.glob("LibreOffice_*_Win_x86-64.msi"))
        return next((path.resolve() for path in candidates if path.is_file()), None)

    def can_install(self) -> bool:
        return os.name == "nt"

    def get_info(self, *, refresh: bool = False) -> dict[str, object]:
        executable = self.find_executable(refresh=refresh)
        version = self.get_version(refresh=refresh) if executable else ""
        available = executable is not None and bool(version)
        managed = self.is_managed(executable)
        return {
            "available": available,
            "engine": "libreoffice",
            "version": version,
            "executable": str(executable) if executable else "",
            "supported_inputs": ["docx", "doc"],
            "diagnostic": (
                "LibreOffice Writer PDF 导出已就绪"
                if available
                else "未检测到可用的 LibreOffice，可在设置中一键安装"
            ),
            "managed": managed,
            "installer_found": self.find_installer() is not None,
            "can_install": self.can_install(),
        }

    def get_install_progress(self) -> dict[str, object]:
        return dict(self._progress)

    async def ensure(self) -> bool:
        return await asyncio.to_thread(self._install_sync)

    def remove(self) -> bool:
        executable = self.find_executable(refresh=True)
        if executable is None:
            self._set_progress(100, "已卸载")
            return True
        if not self.is_managed(executable):
            self._set_progress(0, "系统安装的 LibreOffice 不由 MarkFlow 卸载")
            return False
        try:
            root = self.managed_root.resolve()
            root.relative_to((self.settings.data_dir / "modules").resolve())
            shutil.rmtree(root)
            self._executable = None
            self._version = ""
            self._set_progress(100, "LibreOffice 模块已卸载")
            return True
        except (OSError, ValueError) as exc:
            self._set_progress(0, f"卸载失败：{exc}")
            return False

    def _install_sync(self) -> bool:
        with self._install_lock:
            if self.is_available(refresh=True):
                self._set_progress(100, "LibreOffice 已就绪")
                return True
            if not self.can_install():
                self._set_progress(0, "一键安装当前仅支持 Windows")
                return False
            staging = self.managed_root.with_name("libreoffice.installing")
            promoted = False
            try:
                installer = self.find_installer() or self._download_installer()
                self._set_progress(78, "正在校验安装包...")
                self._verify_installer(installer)
                self._set_progress(82, "正在部署 LibreOffice（约需 1–3 分钟）...")
                if staging.exists():
                    shutil.rmtree(staging)
                staging.parent.mkdir(parents=True, exist_ok=True)
                msiexec = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "msiexec.exe"
                completed = subprocess.run(
                    [
                        str(msiexec),
                        "/a",
                        str(installer),
                        "/qn",
                        "/norestart",
                        f"TARGETDIR={staging}",
                    ],
                    check=False,
                    capture_output=True,
                    timeout=self.settings.libreoffice_install_timeout,
                )
                if completed.returncode not in (0, 3010):
                    detail = completed.stderr.decode(errors="replace").strip()
                    raise RuntimeError(f"Windows Installer 返回 {completed.returncode}: {detail}")
                if self._find_in_root(staging) is None:
                    raise RuntimeError("安装完成，但未找到 soffice 可执行文件")
                if self.managed_root.exists():
                    shutil.rmtree(self.managed_root)
                staging.replace(self.managed_root)
                promoted = True
                self._executable = None
                self._version = ""
                if not self.is_available(refresh=True):
                    raise RuntimeError("LibreOffice 安装后启动检测失败")
                self._set_progress(100, "LibreOffice 安装完成")
                return True
            except Exception as exc:
                if staging.exists():
                    shutil.rmtree(staging, ignore_errors=True)
                if promoted and self.managed_root.exists():
                    shutil.rmtree(self.managed_root, ignore_errors=True)
                self._set_progress(0, f"LibreOffice 安装失败：{exc}")
                return False

    def _download_installer(self) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        destination = self.cache_dir / self.installer_name
        partial = destination.with_suffix(destination.suffix + ".part")
        self._set_progress(2, "正在获取 LibreOffice 官方镜像列表...")
        try:
            sources, expected_sha256, expected_size = self._load_metalink()
            self._expected_sha256 = expected_sha256
        except Exception:
            sources = [self.settings.libreoffice_download_url]
            expected_size = 0

        errors: list[str] = []
        for index, source in enumerate(sources, start=1):
            partial.unlink(missing_ok=True)
            try:
                self._download_from_source(
                    source,
                    partial,
                    expected_size=expected_size,
                    source_index=index,
                    source_count=len(sources),
                )
                partial.replace(destination)
                return destination
            except Exception as exc:
                errors.append(f"{urlparse(source).hostname}: {exc}")
                self._set_progress(
                    4,
                    f"镜像 {index} 下载失败，正在切换备用镜像...",
                )
        partial.unlink(missing_ok=True)
        detail = "; ".join(errors[-3:])
        raise RuntimeError(f"所有 LibreOffice 下载镜像均不可用：{detail}")

    def _load_metalink(self) -> tuple[list[str], str, int]:
        request = self._official_request(f"{self.settings.libreoffice_download_url}.meta4")
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            payload = response.read(2 * 1024 * 1024 + 1)
        if len(payload) > 2 * 1024 * 1024:
            raise RuntimeError("官方镜像列表过大")
        root = ET.fromstring(payload)  # noqa: S314 - fetched from a fixed official HTTPS host.
        namespace = {"m": "urn:ietf:params:xml:ns:metalink"}
        file_node = root.find("m:file", namespace)
        if file_node is None or file_node.get("name") != self.installer_name:
            raise RuntimeError("官方镜像列表中的安装包名称不匹配")
        hash_node = file_node.find("m:hash[@type='sha-256']", namespace)
        expected_sha256 = (hash_node.text or "").strip() if hash_node is not None else ""
        if not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
            raise RuntimeError("官方镜像列表缺少有效 SHA-256")
        size_node = file_node.find("m:size", namespace)
        expected_size = int(size_node.text or "0") if size_node is not None else 0

        entries: list[tuple[str, int, str]] = []
        preferred_locations = {"cn": 0, "hk": 1, "sg": 2, "tw": 3}
        for url_node in file_node.findall("m:url", namespace):
            url = (url_node.text or "").strip()
            parsed = urlparse(url)
            if (
                parsed.scheme != "https"
                or Path(parsed.path).name != self.installer_name
                or not parsed.hostname
            ):
                continue
            location = url_node.get("location", "").casefold()
            priority = int(url_node.get("priority", "9999"))
            entries.append((url, preferred_locations.get(location, 10), priority))
        entries.sort(key=lambda entry: (entry[1], entry[2]))
        sources = [entry[0] for entry in entries[:8]]
        if not sources:
            raise RuntimeError("官方镜像列表中没有可用的 HTTPS 镜像")
        return sources, expected_sha256, expected_size

    def _download_from_source(
        self,
        source: str,
        partial: Path,
        *,
        expected_size: int,
        source_index: int,
        source_count: int,
    ) -> None:
        request = urllib.request.Request(  # noqa: S310 - validated Metalink HTTPS URL.
            source,
            headers={"User-Agent": "MarkFlow LibreOffice Installer"},
        )
        with (
            urllib.request.urlopen(request, timeout=30) as response,  # noqa: S310
            partial.open("wb") as out,
        ):
            header_size = int(response.headers.get("Content-Length", "0"))
            total = expected_size or header_size
            downloaded = 0
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
                downloaded += len(chunk)
                pct = 5 + int(downloaded / total * 68) if total else 35
                self._set_progress(
                    min(pct, 73),
                    f"正在下载 LibreOffice（镜像 {source_index}/{source_count}）...",
                )
        if expected_size and partial.stat().st_size != expected_size:
            raise RuntimeError("下载文件大小不匹配")

    def _verify_installer(self, installer: Path) -> None:
        expected_sha256 = self._expected_sha256
        if not expected_sha256:
            request = self._official_request(self.settings.libreoffice_checksum_url)
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                checksum_text = response.read().decode("ascii", errors="replace")
            match = re.search(r"\b([a-fA-F0-9]{64})\b", checksum_text)
            if match is None:
                raise RuntimeError("官方校验文件格式无效")
            expected_sha256 = match.group(1)
        digest = hashlib.sha256()
        with installer.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest().casefold() != expected_sha256.casefold():
            installer.unlink(missing_ok=True)
            raise RuntimeError("安装包 SHA-256 校验失败，请重试")

    def _find_in_root(self, root: Path) -> Path | None:
        for candidate in (root / "program" / "soffice.com", root / "program" / "soffice.exe"):
            if candidate.is_file():
                return candidate
        for name in ("soffice.com", "soffice.exe"):
            found = next(root.rglob(name), None) if root.exists() else None
            if found:
                return found
        return None

    @staticmethod
    def _official_request(url: str) -> urllib.request.Request:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "download.documentfoundation.org":
            raise RuntimeError("LibreOffice 下载地址必须使用 Document Foundation 官方 HTTPS 源")
        return urllib.request.Request(  # noqa: S310
            url,
            headers={"User-Agent": "MarkFlow LibreOffice Installer"},
        )

    def _set_progress(self, progress: int, message: str) -> None:
        self._progress = {"progress": progress, "message": message}

    def _candidates(self) -> list[Path]:
        candidates: list[Path] = []
        configured = self.settings.libreoffice_path or os.environ.get("MARKFLOW_LIBREOFFICE_PATH")
        if configured:
            configured_path = Path(configured)
            if configured_path.is_dir():
                candidates.extend(
                    configured_path / name for name in ("soffice.com", "soffice.exe", "soffice")
                )
            else:
                candidates.append(configured_path)
        managed = self.managed_root / "program"
        candidates.extend(managed / name for name in ("soffice.com", "soffice.exe"))
        nested_managed = self._find_in_root(self.managed_root)
        if nested_managed:
            candidates.append(nested_managed)
        for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
            root = os.environ.get(variable)
            if root:
                program = Path(root) / "LibreOffice" / "program"
                candidates.extend(program / name for name in ("soffice.com", "soffice.exe"))
        for name in ("soffice.com", "soffice.exe", "soffice"):
            resolved = shutil.which(name)
            if resolved:
                candidates.append(Path(resolved))
        unique: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate).casefold()
            if key not in seen:
                unique.append(candidate)
                seen.add(key)
        return unique
