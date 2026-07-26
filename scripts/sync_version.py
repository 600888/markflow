#!/usr/bin/env python3
"""Sync the backend version to Tauri, Cargo, and frontend metadata."""

from __future__ import annotations

import json
from pathlib import Path
import re
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = PROJECT_ROOT / "backend" / "pyproject.toml"


def _version() -> str:
    with PYPROJECT.open("rb") as file:
        return tomllib.load(file)["project"]["version"]


def _sync_json(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _sync_package_lock(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    root_package = data.get("packages", {}).get("")
    if root_package is not None:
        root_package["version"] = version
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _sync_cargo(path: Path, version: str) -> None:
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(?m)^(version\s*=\s*)"[^"]+"',
        rf'\g<1>"{version}"',
        content,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"Cannot find package version in {path}")
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    version = _version()
    _sync_json(PROJECT_ROOT / "src-tauri" / "tauri.conf.json", version)
    _sync_json(PROJECT_ROOT / "frontend" / "package.json", version)
    package_lock = PROJECT_ROOT / "frontend" / "package-lock.json"
    if package_lock.exists():
        _sync_package_lock(package_lock, version)
    _sync_cargo(PROJECT_ROOT / "src-tauri" / "Cargo.toml", version)
    print(f"[OK] Version synced: {version}")


if __name__ == "__main__":
    main()
