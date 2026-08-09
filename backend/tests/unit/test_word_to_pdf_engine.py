from pathlib import Path

from app.core.word_to_pdf_engine import NativeOfficeWordToPdfEngine


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
