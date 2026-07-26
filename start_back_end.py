"""MarkFlow backend launcher.

Usage:
    python start_back_end.py
    python start_back_end.py --port 62581
    python start_back_end.py --port 62581 --data-dir .\data

This file is also the entry point used by the packaged Tauri sidecar.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MarkFlow Backend")
    parser.add_argument("--host", default=None, help="Listening host")
    parser.add_argument("--port", type=int, default=None, help="Listening port")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory containing bundled data such as the Pandoc installer",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.data_dir is not None:
        os.environ["MARKFLOW_DATA_DIR"] = str(args.data_dir.resolve())

    # The backend uses top-level imports such as ``app`` and ``config``.
    # Add backend/ before importing the application so the same launcher works
    # from the repository root and from a PyInstaller bundle.
    sys.path.insert(0, str(BACKEND_DIR))

    import uvicorn

    from app.main import app, settings

    host = args.host or settings.host
    port = args.port or settings.port
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
