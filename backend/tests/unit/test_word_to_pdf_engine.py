import os
import subprocess
from pathlib import Path

import pytest

from app.core.word_to_pdf_engine import (
    NativeOfficeWordToPdfEngine,
    _windows_creation_flags,
)


@pytest.mark.skipif(os.name != "nt", reason="仅验证 Windows 进程标志")
def test_windows_child_processes_do_not_create_console_window() -> None:
    flags = _windows_creation_flags(new_process_group=True)

    assert flags & subprocess.CREATE_NO_WINDOW
    assert flags & subprocess.CREATE_NEW_PROCESS_GROUP


def test_native_office_script_uses_fixed_format_export_and_cleanup() -> None:
    script = NativeOfficeWordToPdfEngine._build_script(  # noqa: SLF001
        "Word.Application",
        Path(r"C:\input\产品说明.docx"),
        Path(r"C:\output\产品说明.pdf"),
        optimize_for=0,
        bookmarks=1,
    )

    assert "ExportAsFixedFormat" in script
    assert "AutomationSecurity = 3" in script
    assert "Documents.Open($inputPath, $false, $true)" in script
    assert "$doc.Close($false)" in script
    assert "$app.Quit()" in script


def test_native_office_script_escapes_single_quotes() -> None:
    script = NativeOfficeWordToPdfEngine._build_script(  # noqa: SLF001
        "KWPS.Application",
        Path("C:/input/author's-file.docx"),
        Path("C:/output/result.pdf"),
        optimize_for=1,
        bookmarks=0,
    )

    assert "author''s-file.docx" in script
    assert "New-Object -ComObject 'KWPS.Application'" in script
