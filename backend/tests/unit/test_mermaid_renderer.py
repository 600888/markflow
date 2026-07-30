from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw

from app.core.mermaid_renderer import _center_png, _render_one


def _content_box(path: Path):
    with Image.open(path) as source:
        image = source.convert("RGB")
    background = Image.new("RGB", image.size, image.getpixel((0, 0)))
    return image.size, ImageChops.difference(image, background).getbbox()


def test_center_png_produces_equal_margins(tmp_path: Path) -> None:
    output = tmp_path / "diagram.png"
    image = Image.new("RGB", (120, 90), "white")
    ImageDraw.Draw(image).rectangle((17, 13, 94, 68), fill="black")
    image.save(output)

    assert _center_png(output, padding=12)

    size, box = _content_box(output)
    assert box is not None
    left, top, right, bottom = box
    assert (left, top, size[0] - right, size[1] - bottom) == (12, 12, 12, 12)


def test_center_png_rejects_already_clipped_content(tmp_path: Path) -> None:
    output = tmp_path / "clipped.png"
    image = Image.new("RGB", (120, 90), "white")
    ImageDraw.Draw(image).rectangle((17, 13, 119, 68), fill="black")
    image.save(output)

    assert not _center_png(output, padding=12)


async def test_render_one_retries_when_edge_does_not_create_screenshot(
    tmp_path: Path,
) -> None:
    html_path = tmp_path / "diagram.html"
    html_path.write_text("<html></html>", encoding="utf-8")
    output_path = tmp_path / "diagram.png"
    calls = 0

    async def fake_run_edge(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return 0, b"<title>120x90</title>", b""
        if calls == 3:
            image = Image.new("RGB", (648, 558), "white")
            ImageDraw.Draw(image).rectangle((48, 48, 200, 150), fill="black")
            image.save(output_path)
        return 0, b"", b""

    with (
        patch("app.core.mermaid_renderer._find_edge", return_value="edge.exe"),
        patch("app.core.mermaid_renderer._run_edge", side_effect=fake_run_edge),
    ):
        assert await _render_one(html_path, output_path)

    assert calls == 3
