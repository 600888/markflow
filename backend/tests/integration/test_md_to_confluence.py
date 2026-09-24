"""Markdown 到两种 Confluence 格式的实际 Pandoc 转换。"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pypandoc
import pytest

from app.core.engine import PandocEngine
from app.models import OutputFormat


@pytest.mark.asyncio
async def test_confluence_wiki_conversion(tmp_path: Path) -> None:
    try:
        pypandoc.get_pandoc_path()
    except OSError:
        pytest.skip("Pandoc 未安装")

    source = tmp_path / "page.md"
    source.write_text(
        "# 标题\n\n**粗体** 和 [链接](https://example.com)\n\n"
        "```python\nprint(1)\n```\n\n"
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "![图示](assets/figure.png)\n",
        encoding="utf-8",
    )
    result = await PandocEngine().convert(
        source,
        OutputFormat.CONFLUENCE,
        convert_mermaid=False,
    )

    assert result.output_path.suffix == ".wiki"
    content = result.output_path.read_text(encoding="utf-8")
    assert "h1." in content
    assert "{code:python}" in content
    assert "[链接|https://example.com]" in content
    assert "|| A || B ||" in content
    assert "!figure.png" in content


@pytest.mark.asyncio
async def test_confluence_storage_conversion(tmp_path: Path) -> None:
    try:
        pypandoc.get_pandoc_path()
    except OSError:
        pytest.skip("Pandoc 未安装")

    source = tmp_path / "page.md"
    source.write_text(
        "# 标题\n\n**粗体** 和 [链接](https://example.com)\n\n"
        '```python\nprint("]]>")\n```\n\n'
        "![图示](assets/figure.png)\n",
        encoding="utf-8",
    )
    result = await PandocEngine().convert(
        source,
        OutputFormat.CONFLUENCE_STORAGE,
        convert_mermaid=False,
    )

    assert result.output_path.suffix == ".xml"
    root = ET.fromstring(result.output_path.read_text(encoding="utf-8"))  # noqa: S314
    assert root.find("h1") is not None
    assert root.find("p/strong") is not None
    ns = {
        "ac": "http://atlassian.com/content",
        "ri": "http://atlassian.com/resource/identifier",
    }
    code = root.find("ac:structured-macro", ns)
    assert code is not None
    assert code.attrib["{http://atlassian.com/content}name"] == "code"
    assert code.find("ac:parameter", ns).text == "python"
    assert code.find("ac:plain-text-body", ns).text == 'print("]]>")'
    image = root.find("ac:image/ri:attachment", ns)
    assert image is not None
    assert image.attrib["{http://atlassian.com/resource/identifier}filename"] == "figure.png"
