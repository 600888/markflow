from pathlib import Path

import pytest

from app.core.word_to_pdf_engine import LibreOfficeWordToPdfEngine
from app.models import OutputFormat
from app.utils.config import AppSettings
from app.utils.exceptions import ConversionError


class FakeManager:
    def __init__(self, executable: Path) -> None:
        self.executable = executable

    def find_executable(self):
        return self.executable

    def get_version(self):
        return "26.2.0"

    def is_available(self):
        return True


class FakeProcess:
    returncode = 0

    async def communicate(self):
        return b"convert ok", b""


@pytest.mark.asyncio
async def test_engine_builds_isolated_command_and_validates_pdf(tmp_path, monkeypatch) -> None:
    executable = tmp_path / "soffice.com"
    executable.write_bytes(b"")
    source = tmp_path / "产品说明.docx"
    source.write_bytes(b"word")
    commands: list[tuple[str, ...]] = []

    async def fake_create_subprocess_exec(*command, **kwargs):
        commands.append(command)
        output_dir = Path(command[command.index("--outdir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240
        (output_dir / "产品说明.pdf").write_bytes(b"%PDF-1.7\nmock")
        return FakeProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    settings = AppSettings(data_dir=tmp_path, word_conversion_timeout=5)
    engine = LibreOfficeWordToPdfEngine(settings, FakeManager(executable))

    result = await engine.convert(
        source,
        OutputFormat.PDF,
        options={
            "quality": "screen",
            "export_bookmarks": False,
            "embed_standard_fonts": True,
        },
    )

    assert result.output_path.read_bytes().startswith(b"%PDF-")
    command = commands[0]
    assert any(part.startswith("-env:UserInstallation=file:") for part in command)
    filter_spec = command[command.index("--convert-to") + 1]
    assert '"MaxImageResolution":{"type":"long","value":"150"}' in filter_spec
    assert '"ExportBookmarks":{"type":"boolean","value":"false"}' in filter_spec


def test_quality_preset_rejects_unknown_value() -> None:
    with pytest.raises(ConversionError, match="质量选项"):
        LibreOfficeWordToPdfEngine._build_filter_spec(  # noqa: SLF001
            {"quality": "ultra"}
        )
