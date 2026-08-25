# ruff: noqa: INP001
"""Build Great Docs with an explicitly resolved Quarto executable."""

from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    """Expose Quarto to Great Docs, then build the documentation site."""
    configured_path = os.environ.get("MARKFLOW_QUARTO_PATH", "").strip()
    if not configured_path:
        msg = "MARKFLOW_QUARTO_PATH is not configured"
        raise RuntimeError(msg)

    quarto_path = Path(configured_path)
    if not quarto_path.is_file():
        msg = f"Quarto executable not found: {quarto_path}"
        raise FileNotFoundError(msg)

    current_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{quarto_path.parent}{os.pathsep}{current_path}"

    from great_docs import GreatDocs

    GreatDocs().build()


if __name__ == "__main__":
    main()
