#!/usr/bin/env python3
"""下载 mermaid.min.js 到 backend/static/ 目录"""

from __future__ import annotations

from pathlib import Path

MERMAIN_JS_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
STATIC_DIR = Path(__file__).resolve().parent.parent / "backend" / "static"


def main() -> None:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    target = STATIC_DIR / "mermaid.min.js"

    if target.exists() and target.stat().st_size > 1_000_000:
        print(f"[OK] mermaid.min.js 已存在 ({target.stat().st_size // 1024} KB)")
        return

    import urllib.request

    print("正在下载 mermaid.min.js...")
    urllib.request.urlretrieve(MERMAIN_JS_URL, str(target))
    size = target.stat().st_size
    print(f"[OK] 下载完成: {target} ({size // 1024} KB)")


if __name__ == "__main__":
    main()
