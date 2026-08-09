"""检测可用于 Word 固定版式导出的本机 Office 应用。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


class NativeOfficeManager:
    """通过 COM 注册信息和常见安装路径检测 Word/WPS。"""

    def __init__(
        self,
        engine_id: str,
        name: str,
        prog_ids: tuple[str, ...],
        executable_names: tuple[str, ...],
    ) -> None:
        self.engine_id = engine_id
        self.name = name
        self.prog_ids = prog_ids
        self.executable_names = executable_names

    def find_prog_id(self) -> str | None:
        """返回第一个已注册的 COM ProgID。"""
        if os.name != "nt":
            return None
        try:
            import winreg

            for prog_id in self.prog_ids:
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CLASSES_ROOT,
                        rf"{prog_id}\CLSID",
                    ):
                        return prog_id
                except OSError:
                    continue
        except ImportError:
            return None
        return None

    def find_executable(self) -> Path | None:
        """返回应用可执行文件路径（仅用于状态展示）。"""
        for name in self.executable_names:
            if found := shutil.which(name):
                return Path(found)
            if registered := self._find_app_path(name):
                return registered

        candidates = self._common_candidates()
        return next((path for path in candidates if path.is_file()), None)

    def get_info(self, *, refresh: bool = False) -> dict[str, object]:
        """返回前端可消费的引擎状态。"""
        del refresh
        prog_id = self.find_prog_id()
        executable = self.find_executable()
        available = prog_id is not None
        if available:
            diagnostic = f"{self.name} 原生导出接口已就绪"
        elif os.name != "nt":
            diagnostic = f"{self.name} 原生导出仅支持 Windows"
        elif executable:
            diagnostic = f"检测到 {self.name}，但未注册自动化导出接口"
        else:
            diagnostic = f"未检测到可用的 {self.name}"
        return {
            "id": self.engine_id,
            "name": self.name,
            "available": available,
            "version": self._registered_version(prog_id),
            "executable": str(executable or ""),
            "prog_id": prog_id or "",
            "supported_inputs": ["docx", "doc"],
            "diagnostic": diagnostic,
            "fidelity": "native",
        }

    @staticmethod
    def _find_app_path(executable_name: str) -> Path | None:
        if os.name != "nt":
            return None
        try:
            import winreg

            key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{executable_name}"
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for access in (winreg.KEY_READ, winreg.KEY_READ | winreg.KEY_WOW64_32KEY):
                    try:
                        with winreg.OpenKey(root, key_path, 0, access) as key:
                            value = Path(str(winreg.QueryValue(key, None)).strip('"'))
                            if value.is_file():
                                return value
                    except OSError:
                        continue
        except ImportError:
            return None
        return None

    def _common_candidates(self) -> list[Path]:
        program_files = [
            Path(value)
            for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")
            if (value := os.environ.get(key))
        ]
        if self.engine_id == "microsoft-word":
            return [
                root / "Microsoft Office" / "root" / "Office16" / "WINWORD.EXE"
                for root in program_files
            ] + [
                root / "Microsoft Office" / "Office16" / "WINWORD.EXE"
                for root in program_files
            ]

        candidates: list[Path] = []
        for root in program_files:
            candidates.extend(
                [
                    root / "Kingsoft" / "WPS Office" / "office6" / "wps.exe",
                    root / "Kingsoft" / "WPS Office" / "ksolaunch.exe",
                ]
            )
            version_root = root / "Kingsoft" / "WPS Office"
            if version_root.is_dir():
                candidates.extend(version_root.glob("*\\office6\\wps.exe"))
        return candidates

    @staticmethod
    def _registered_version(prog_id: str | None) -> str:
        if not prog_id:
            return ""
        suffix = prog_id.rsplit(".", 1)[-1]
        return suffix if suffix.isdigit() else ""


word_manager = NativeOfficeManager(
    "microsoft-word",
    "Microsoft Word",
    ("Word.Application",),
    ("WINWORD.EXE",),
)

wps_manager = NativeOfficeManager(
    "wps",
    "WPS Office",
    ("KWPS.Application", "wps.Application"),
    ("wps.exe",),
)
