# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


PROJECT_ROOT = Path(SPECPATH).resolve()
BACKEND_DIR = PROJECT_ROOT / "backend"
BUILD_MODE = os.environ.get("MARKFLOW_PYINSTALLER_MODE", "onedir").lower()
APP_NAME = os.environ.get("MARKFLOW_PYINSTALLER_NAME", "markflow-service")
CONTENTS_DIRECTORY = os.environ.get(
    "MARKFLOW_PYINSTALLER_CONTENTS_DIR",
    "markflow-service-runtime",
)
CONSOLE = os.environ.get("MARKFLOW_PYINSTALLER_CONSOLE", "0") == "1"

if BUILD_MODE not in {"onefile", "onedir"}:
    raise ValueError(f"Unsupported MARKFLOW_PYINSTALLER_MODE: {BUILD_MODE}")

datas = [
    (str(BACKEND_DIR / "pyproject.toml"), "."),
    (str(BACKEND_DIR / "templates"), "templates"),
    (str(BACKEND_DIR / "filters"), "filters"),
    (str(BACKEND_DIR / "static"), "static"),
    (str(BACKEND_DIR / "migrations"), "migrations"),
]
# RapidOCR 的 ONNX 模型与配置、magika 的文件类型检测模型均为运行时必需的数据文件
datas += collect_data_files("rapidocr_onnxruntime")
datas += collect_data_files("magika")

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "sse_starlette",
    "sqlalchemy",
    "sqlalchemy.dialects.sqlite",
    "alembic",
    "alembic.ddl.sqlite",
    "alembic.runtime.migration",
    "mako",
    # Word/PDF 转 Markdown（MarkItDown 及其转换器）
    "markitdown",
    "mammoth",
    "pdfminer",
    "pdfminer.high_level",
    "magika",
    "onnxruntime",
    "fitz",
    "pymupdf",
    # 图片 OCR（RapidOCR）
    "rapidocr_onnxruntime",
    "cv2",
]

a = Analysis(
    [str(PROJECT_ROOT / "start_back_end.py")],
    pathex=[str(PROJECT_ROOT), str(BACKEND_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6",
        "scipy",
        "pandas",
        "matplotlib",
        "tkinter",
        "_tkinter",
    ],
    noarchive=False,
    optimize=0,
)
# OCR 仅使用 cv2 的图像处理能力，剔除视频 I/O DLL（约 30MB）
a.binaries = [
    item
    for item in a.binaries
    if "opencv_videoio_ffmpeg" not in item[0].lower()
]
pyz = PYZ(a.pure)

if BUILD_MODE == "onefile":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=CONSOLE,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=CONSOLE,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        contents_directory=CONTENTS_DIRECTORY,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name=APP_NAME,
    )
