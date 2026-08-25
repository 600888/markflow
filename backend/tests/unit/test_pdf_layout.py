"""PDF 版面感知 Markdown 重建测试。"""

from __future__ import annotations

from pathlib import Path

from app.core.pdf_layout import convert_pdf_layout


def _draw_table(page, rows: list[list[str]]) -> None:
    import pymupdf

    columns = [72.0, 210.0, 360.0, 520.0]
    top = 90.0
    row_height = 32.0
    fill = (0.94, 0.94, 0.94)
    line_fill = (0.7, 0.7, 0.7)
    for column in range(len(columns) - 1):
        page.draw_rect(
            pymupdf.Rect(columns[column], top, columns[column + 1], top + row_height),
            color=None,
            fill=fill,
        )
    for row_index, row in enumerate(rows):
        row_top = top + row_index * row_height
        for column, value in enumerate(row):
            page.insert_text(
                (columns[column] + 8, row_top + 20),
                value,
                fontsize=11,
            )
        boundary = row_top + row_height
        for column in range(len(columns) - 1):
            page.draw_rect(
                pymupdf.Rect(
                    columns[column],
                    boundary,
                    columns[column + 1],
                    boundary + 0.75,
                ),
                color=None,
                fill=line_fill,
            )


def _create_cross_page_table_pdf(path: Path) -> None:
    import pymupdf

    document = pymupdf.open()
    first = document.new_page()
    first.insert_text((72, 60), "First section", fontsize=16, fontname="hebo")
    _draw_table(first, [["Name", "Unit", "Description"], ["Power", "kW", "Active"]])
    second = document.new_page()
    _draw_table(second, [["Name", "Unit", "Description"], ["Voltage", "V", "Grid"]])
    document.save(path)
    document.close()


def test_convert_pdf_layout_extracts_and_merges_cross_page_table(tmp_path) -> None:
    source = tmp_path / "table.pdf"
    _create_cross_page_table_pdf(source)

    markdown = convert_pdf_layout(
        source,
        tmp_path / "assets" / "media",
        extract_tables=True,
        extract_images=False,
    )

    assert "# First section" in markdown
    assert markdown.count("| Name | Unit | Description |") == 1
    assert "| Power | kW | Active |" in markdown
    assert "| Voltage | V | Grid |" in markdown
    assert markdown.index("Power") < markdown.index("Voltage")
