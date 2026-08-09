from __future__ import annotations

import asyncio
import hashlib
import urllib.error
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.libreoffice_check import LibreOfficeManager
from app.utils.config import AppSettings


class _Response(BytesIO):
    def __init__(self, value: bytes, headers: dict[str, str] | None = None) -> None:
        super().__init__(value)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_get_info_detects_managed_copy(tmp_path, monkeypatch) -> None:
    manager = LibreOfficeManager(AppSettings(data_dir=tmp_path))
    executable = manager.managed_root / "program" / "soffice.com"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"stub")
    monkeypatch.setattr(
        "app.core.libreoffice_check.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=b"LibreOffice 26.2.5.2", stderr=b""
        ),
    )

    info = manager.get_info(refresh=True)

    assert info["available"] is True
    assert info["managed"] is True
    assert info["version"] == "26.2.5.2"


def test_verify_installer_rejects_modified_download(tmp_path, monkeypatch) -> None:
    manager = LibreOfficeManager(AppSettings(data_dir=tmp_path))
    installer = tmp_path / "LibreOffice.msi"
    installer.write_bytes(b"modified")
    expected = hashlib.sha256(b"official").hexdigest().encode()
    monkeypatch.setattr(
        "app.core.libreoffice_check.urllib.request.urlopen",
        lambda *args, **kwargs: _Response(expected),
    )

    with pytest.raises(RuntimeError, match="SHA-256"):
        manager._verify_installer(installer)  # noqa: SLF001
    assert not installer.exists()


def test_download_switches_to_backup_mirror_on_certificate_error(tmp_path, monkeypatch) -> None:
    manager = LibreOfficeManager(AppSettings(data_dir=tmp_path))
    payload = b"msi"
    digest = hashlib.sha256(payload).hexdigest()
    meta4 = f"""<?xml version="1.0" encoding="UTF-8"?>
    <metalink xmlns="urn:ietf:params:xml:ns:metalink">
      <file name="{manager.installer_name}">
        <size>{len(payload)}</size>
        <hash type="sha-256">{digest}</hash>
        <url location="cn" priority="1">https://expired.example/{manager.installer_name}</url>
        <url location="sg" priority="2">https://backup.example/{manager.installer_name}</url>
      </file>
    </metalink>""".encode()
    requested: list[str] = []

    def fake_urlopen(request, **kwargs):
        requested.append(request.full_url)
        if request.full_url.endswith(".meta4"):
            return _Response(meta4)
        if "expired.example" in request.full_url:
            raise urllib.error.URLError("certificate has expired")
        return _Response(payload, {"Content-Length": str(len(payload))})

    monkeypatch.setattr("app.core.libreoffice_check.urllib.request.urlopen", fake_urlopen)

    installer = manager._download_installer()  # noqa: SLF001

    assert installer.read_bytes() == payload
    assert manager._expected_sha256 == digest  # noqa: SLF001
    assert any("expired.example" in url for url in requested)
    assert any("backup.example" in url for url in requested)


def test_remove_does_not_delete_system_install(tmp_path) -> None:
    executable = tmp_path / "system-libreoffice" / "soffice.com"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"stub")
    settings = AppSettings(data_dir=tmp_path / "data", libreoffice_path=executable)
    manager = LibreOfficeManager(settings)

    assert manager.remove() is False
    assert executable.exists()
    assert "不由 MarkFlow 卸载" in str(manager.get_install_progress()["message"])


def test_install_deploys_private_copy(tmp_path, monkeypatch) -> None:
    manager = LibreOfficeManager(AppSettings(data_dir=tmp_path))
    installer = tmp_path / manager.installer_name
    installer.write_bytes(b"msi")
    monkeypatch.setattr(manager, "can_install", lambda: True)
    monkeypatch.setattr(manager, "find_installer", lambda: installer)
    monkeypatch.setattr(manager, "_verify_installer", lambda _path: None)

    def fake_run(command, **kwargs):
        if command[1] == "--version":
            return SimpleNamespace(returncode=0, stdout=b"LibreOffice 26.2.5.2", stderr=b"")
        target = next(arg.split("=", 1)[1] for arg in command if arg.startswith("TARGETDIR="))
        staged = Path(target) / "program" / "soffice.com"
        staged.parent.mkdir(parents=True)
        staged.write_bytes(b"stub")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr("app.core.libreoffice_check.subprocess.run", fake_run)

    assert asyncio.run(manager.ensure()) is True
    assert (manager.managed_root / "program" / "soffice.com").exists()
    assert manager.get_install_progress()["progress"] == 100
