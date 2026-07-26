"""Tests for Word reference template generation."""

from io import BytesIO

from docx import Document

from app.services.template_generator import TemplateGenerator


def test_heading4_is_not_italic_when_omitted() -> None:
    generator = TemplateGenerator()

    result = generator.generate_reference(
        {
            "body": {
                "font": "Arial",
                "size": 11,
            },
        },
    )

    document = Document(BytesIO(result))
    assert document.styles["Heading 4"].font.italic is False


def test_heading4_can_be_explicitly_italic() -> None:
    generator = TemplateGenerator()

    result = generator.generate_reference(
        {
            "heading4": {
                "font": "Arial",
                "size": 11,
                "italic": True,
            },
        },
    )

    document = Document(BytesIO(result))
    assert document.styles["Heading 4"].font.italic is True
