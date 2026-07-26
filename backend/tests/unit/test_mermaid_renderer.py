from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from app.core.mermaid_renderer import _center_png


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
