import io
import zipfile

import pytest

from app.services.word_file_validator import OLE_SIGNATURE, WordFileValidator
from app.utils.exceptions import InvalidWordFileError


def _docx_bytes(document: bytes = b"<w:document />") -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types />")
        archive.writestr("word/document.xml", document)
    return stream.getvalue()


def test_accepts_structurally_valid_docx_and_doc() -> None:
    validator = WordFileValidator()

    assert validator.validate(_docx_bytes(), "报告.DOCX") == ".docx"
    assert validator.validate(OLE_SIGNATURE + b"legacy", "报告.doc") == ".doc"


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (b"not-a-zip", "fake.docx"),
        (b"not-an-ole", "fake.doc"),
        (_docx_bytes(), "fake.docm"),
        (b"", "empty.docx"),
    ],
)
def test_rejects_invalid_word_files(content: bytes, filename: str) -> None:
    with pytest.raises(InvalidWordFileError):
        WordFileValidator().validate(content, filename)


def test_rejects_docx_with_excessive_compression_ratio() -> None:
    content = _docx_bytes(b"0" * 100_000)

    with pytest.raises(InvalidWordFileError, match="压缩比"):
        WordFileValidator(max_compression_ratio=10).validate(content, "bomb.docx")
