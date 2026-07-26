"""
Edge headless 驱动的 Mermaid 图表渲染器

使用 Windows 自带的 Microsoft Edge (WebView2) 进行 headless 渲染，
无需额外下载 Chromium 或安装任何浏览器。

用法:
    from app.core.mermaid_renderer import render_diagrams
    success = await render_diagrams([(code1, path1), (code2, path2)])
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from app.core.log import log

# ── 模块级缓存 ──────────────────────────────────────────
_MERMAID_JS: str | None = None
_EDGE_PATH: str | None = None


def _find_edge() -> str | None:
    """查找 Microsoft Edge 可执行文件路径"""
    global _EDGE_PATH  # noqa: PLW0603
    if _EDGE_PATH:
        return _EDGE_PATH

    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for c in candidates:
        if c.exists():
            _EDGE_PATH = str(c)
            return _EDGE_PATH

    # 尝试从 PATH 查找
    found = shutil.which("msedge")
    if found:
        _EDGE_PATH = found
        return _EDGE_PATH

    return None


def _load_mermaid_js() -> str:
    """加载内嵌的 mermaid.min.js"""
    global _MERMAID_JS  # noqa: PLW0603
    if _MERMAID_JS is not None:
        return _MERMAID_JS

    from config.paths import DATA_ROOT

    candidates = [
        DATA_ROOT / "static" / "mermaid.min.js",
        DATA_ROOT / "backend" / "static" / "mermaid.min.js",
        Path(__file__).resolve().parent.parent.parent / "static" / "mermaid.min.js",
    ]
    for js_path in candidates:
        if js_path.exists():
            _MERMAID_JS = js_path.read_text(encoding="utf-8")
            log.debug(f"已加载 mermaid.js ({len(_MERMAID_JS)} bytes): {js_path}")
            return _MERMAID_JS

    log.warning("mermaid.min.js 未找到，Mermaid 图表将无法渲染")
    _MERMAID_JS = ""
    return ""


def _build_html(diagram_code: str, theme: str = "default") -> str:
    """生成自包含的 HTML 页面（含自动尺寸检测 JS）"""
    mermaid_js = _load_mermaid_js()
    if not mermaid_js:
        return ""

    escaped_code = diagram_code.replace("</script>", "<\\/script>")

    background = "#0b0b0b" if theme == "dark" else "#ffffff"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ width:100%; height:100%; }}
  body {{
    background:{background};
    min-width:100px;
    min-height:100px;
    overflow:hidden;
  }}
  .mermaid {{
    position:absolute;
    left:16px;
    top:16px;
    display:block;
  }}
  .mermaid svg {{ display:block; }}
</style></head><body>
<div class="mermaid">
{escaped_code}
</div>
<script>{mermaid_js}</script>
<script>
(async function() {{
  mermaid.initialize({{
    startOnLoad: false,
    securityLevel: 'strict',
    theme: '{theme}'
  }});
  await mermaid.run({{ querySelector: '.mermaid' }});
  var svg = document.querySelector('.mermaid svg');
  if (svg) {{
    var rect = svg.getBoundingClientRect();
    var width = Math.ceil(rect.width);
    var height = Math.ceil(rect.height);
    var container = document.querySelector('.mermaid');
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    svg.style.width = width + 'px';
    svg.style.height = height + 'px';
    svg.style.maxWidth = 'none';
    container.style.width = width + 'px';
    container.style.height = height + 'px';
    var pad = 32;
    document.title = (width + pad) + 'x' + (height + pad);
  }} else {{
    document.title = 'FAILED';
  }}
}})();
</script></body></html>"""


def is_available() -> bool:
    """检查渲染是否就绪（Edge + mermaid.js）"""
    if not _load_mermaid_js():
        return False
    return _find_edge() is not None


def _center_png(output_path: Path, padding: int = 48) -> bool:
    """按实际非背景像素裁边，再放回四周等距留白的画布。"""
    from PIL import Image, ImageChops

    with Image.open(output_path) as source:
        image = source.convert("RGB")

    background_color = image.getpixel((0, 0))
    background = Image.new("RGB", image.size, background_color)
    content_box = ImageChops.difference(image, background).getbbox()
    if content_box is None:
        return False
    left, top, right, bottom = content_box
    if left <= 0 or top <= 0 or right >= image.width or bottom >= image.height:
        log.warning(
            "Mermaid 图形触及截图边界，拒绝导出可能被裁切的 PNG: "
            f"image={image.size}, content_box={content_box}"
        )
        return False

    content = image.crop(content_box)
    centered = Image.new(
        "RGB",
        (content.width + padding * 2, content.height + padding * 2),
        background_color,
    )
    centered.paste(content, (padding, padding))
    centered.save(output_path, format="PNG")
    return True


async def _render_one(html_path: Path, output_path: Path) -> bool:
    """用 Edge headless 渲染单个 HTML 到 PNG（自适应尺寸）"""
    edge = _find_edge()
    if not edge:
        log.warning("未找到 Microsoft Edge，无法渲染 Mermaid 图表")
        return False

    try:
        # 第 1 步：渲染并获取 SVG 实际尺寸（通过 document.title）
        proc = await asyncio.create_subprocess_exec(
            edge,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--virtual-time-budget=8000",
            "--dump-dom",
            f"file:///{html_path.resolve().as_posix()}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        dom = stdout.decode("utf-8", errors="replace")

        # 从 <title> 解析尺寸：WxH
        import re as _re

        size_match = _re.search(r"<title>(\d+)x(\d+)</title>", dom)
        if size_match:
            svg_w, svg_h = int(size_match[1]), int(size_match[2])
        else:
            # 回退：尝试从 viewBox 解析
            vb = _re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ([\d.]+)"', dom)
            if vb:
                svg_w, svg_h = int(float(vb[1])) + 16, int(float(vb[2])) + 16
            else:
                svg_w, svg_h = 800, 600

        svg_w = max(svg_w, 100)  # 最小 100px
        svg_h = max(svg_h, 100)

        log.debug(f"Mermaid 尺寸: {svg_w}x{svg_h}")

        # 第 2 步：用正确尺寸 + 3x 高清截图
        proc2 = await asyncio.create_subprocess_exec(
            edge,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--screenshot={output_path.resolve()}",
            f"--window-size={svg_w},{svg_h}",
            "--force-device-scale-factor=3",
            "--virtual-time-budget=8000",
            f"file:///{html_path.resolve().as_posix()}",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr2 = await asyncio.wait_for(proc2.communicate(), timeout=20)

        if proc2.returncode != 0 or not output_path.exists():
            err = stderr2.decode("utf-8", errors="replace")[:200] if stderr2 else ""
            log.warning(f"Edge 截图失败 (exit={proc2.returncode}): {err}")
            return False

        if not _center_png(output_path):
            log.warning("Mermaid 截图未检测到有效图形内容")
            return False

        if output_path.stat().st_size < 100:
            log.warning(f"Mermaid 截图过小 ({output_path.stat().st_size} bytes)")
            return False

        return True

    except asyncio.TimeoutError:
        log.warning("Edge 渲染超时")
        return False
    except FileNotFoundError:
        log.warning(f"Edge 可执行文件不存在: {edge}")
        return False
    except Exception as e:
        log.warning(f"Edge 渲染异常: {e}")
        return False


async def render_diagrams(
    diagrams: list[tuple[str, Path]],
    theme: str = "default",
) -> list[bool]:
    """批量渲染 Mermaid 图表（逐个处理，Edge 启动开销很小）"""
    if not diagrams:
        return []

    if not _load_mermaid_js():
        log.warning("mermaid.min.js 未加载，跳过 Mermaid 渲染")
        return [False] * len(diagrams)

    if not _find_edge():
        log.warning("未找到 Microsoft Edge，无法渲染 Mermaid 图表")
        return [False] * len(diagrams)

    results: list[bool] = []
    html_files: list[Path] = []

    # 准备 HTML 文件
    for code, _ in diagrams:
        html_content = _build_html(code, theme=theme)
        if not html_content:
            html_files.append(Path())
            continue
        tmp = Path(tempfile.mktemp(suffix=".html"))  # noqa: S306
        tmp.write_text(html_content, encoding="utf-8")
        html_files.append(tmp)

    # 逐个渲染
    for i, (_, output_path) in enumerate(diagrams):
        if i >= len(html_files) or not html_files[i].exists():
            results.append(False)
            continue

        success = await _render_one(html_files[i], output_path)
        results.append(success)
        if success:
            log.debug(
                f"Mermaid 图表 #{i} 渲染成功: "
                f"{output_path.name} ({output_path.stat().st_size} bytes)"
            )
        else:
            log.warning(f"Mermaid 图表 #{i} 渲染失败，保留原文")

    # 清理临时文件
    for f in html_files:
        if f.exists():
            with contextlib.suppress(OSError):
                f.unlink()

    return results


async def render_diagram(
    diagram_code: str,
    output_path: Path,
    theme: str = "default",
) -> bool:
    """渲染单个 Mermaid 图表"""
    results = await render_diagrams([(diagram_code, output_path)], theme=theme)
    return results[0] if results else False


def get_diagnostic_message() -> str:
    """返回渲染器状态诊断信息"""
    parts: list[str] = []

    js = _load_mermaid_js()
    parts.append("✓ mermaid.js" if js else "✗ mermaid.min.js 未找到")

    edge = _find_edge()
    parts.append(f"✓ Edge ({edge})" if edge else "✗ Edge 未找到")

    return " | ".join(parts)
