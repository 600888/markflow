"""
Playwright 驱动的 Mermaid 图表渲染器

在启动时通过 browser_check.ensure_chromium() 自动下载 Chromium。
此文件仅保留渲染逻辑，不再包含 Chromium 安装或 mmdc 回退。

使用方式:
  from app.core.mermaid_renderer import render_diagrams

  success = await render_diagrams([(code1, path1), (code2, path2)])
"""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path

from app.core.log import log

# ── 模块级缓存 ──────────────────────────────────────────
_MERMAID_JS: str | None = None


def _load_mermaid_js() -> str:
    """加载内嵌的 mermaid.min.js"""
    global _MERMAID_JS  # noqa: PLW0603
    if _MERMAID_JS is not None:
        return _MERMAID_JS

    # 使用 config.paths 获取正确的根目录（处理 PyInstaller 打包路径）
    from config.paths import DATA_ROOT

    candidates = [
        # PyInstaller 打包后: _MEIPASS/static/mermaid.min.js
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


def _build_html(diagram_code: str) -> str:
    """生成自包含的 HTML 页面，内嵌 mermaid.js 用于渲染图表"""
    mermaid_js = _load_mermaid_js()
    if not mermaid_js:
        return ""

    # 防止 XSS / script 闭合
    escaped_code = diagram_code.replace("</script>", "<\\/script>")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: transparent;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    min-height: 100vh;
  }}
  .mermaid {{ display: inline-block; }}
</style>
</head>
<body>
<div class="mermaid">
{escaped_code}
</div>
<script>
{mermaid_js}
</script>
<script>
mermaid.initialize({{
  startOnLoad: true,
  theme: 'default',
  securityLevel: 'loose'
}});
</script>
</body>
</html>"""


def is_available() -> bool:
    """检查 Mermaid 渲染是否就绪（mermaid.js 已加载 + Chromium 已安装）"""
    if not _load_mermaid_js():
        return False
    from app.core.browser_check import chromium_manager

    return chromium_manager.check()


# 渲染视口尺寸（足够大，确保复杂流程图不会被 CSS 缩放）
_VIEWPORT_SIZE = {"width": 4096, "height": 4096}


async def render_diagrams(
    diagrams: list[tuple[str, Path]],
    scale: float = 3.0,
) -> list[bool]:
    """
    批量渲染 Mermaid 图表（共享浏览器会话）

    Args:
        diagrams: [(diagram_code, output_png_path), ...]
        scale: 设备像素比，3.0 表示 3x（高清输出）

    Returns:
        每个图表的渲染成功状态列表

    """
    if not diagrams:
        return []

    if not _load_mermaid_js():
        log.warning("mermaid.min.js 未加载，跳过 Mermaid 渲染")
        return [False] * len(diagrams)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.warning(
            "playwright 未安装，无法渲染 Mermaid 图表。"
            "请运行: pip install playwright && playwright install chromium"
        )
        return [False] * len(diagrams)

    # 准备 HTML 文件
    html_files: list[Path] = []
    for code, _ in diagrams:
        html_content = _build_html(code)
        if not html_content:
            html_files.append(Path())
            continue
        # 在系统临时目录创建 HTML 文件
        tmp = Path(tempfile.mktemp(suffix=".html"))  # noqa: S306
        tmp.write_text(html_content, encoding="utf-8")
        html_files.append(tmp)

    results: list[bool] = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
            )

            for i, (_, output_path) in enumerate(diagrams):
                if i >= len(html_files) or not html_files[i].exists():
                    results.append(False)
                    continue

                page = None
                try:
                    page = await browser.new_page(
                        viewport=_VIEWPORT_SIZE,
                        device_scale_factor=scale,
                    )
                    await page.goto(
                        html_files[i].as_uri(),
                        wait_until="networkidle",
                        timeout=30000,
                    )

                    # 等待 mermaid 渲染完成
                    try:
                        await page.wait_for_selector(
                            ".mermaid svg",
                            timeout=30000,
                        )
                    except Exception:
                        log.warning(f"Mermaid 图表 #{i} 渲染超时（可能语法错误）")
                        results.append(False)
                        continue

                    # 截图
                    el = await page.query_selector(".mermaid")
                    if el:
                        await el.screenshot(path=str(output_path))
                        success = output_path.exists() and output_path.stat().st_size > 0
                        results.append(success)
                        if success:
                            log.debug(
                                f"Mermaid 图表 #{i} 渲染成功: "
                                f"{output_path.name} ({output_path.stat().st_size} bytes)"
                            )
                        else:
                            log.warning(f"Mermaid 图表 #{i} 截图为空")
                    else:
                        log.warning(f"Mermaid 图表 #{i} 未找到渲染元素")
                        results.append(False)

                except Exception as e:
                    log.warning(f"Mermaid 图表 #{i} 渲染异常: {e}")
                    results.append(False)
                finally:
                    if page is not None:
                        await page.close()

            await browser.close()

    except Exception as e:
        log.warning(f"Playwright 浏览器启动失败: {e}")
        results = [False] * len(diagrams)

    finally:
        # 清理临时 HTML 文件
        for f in html_files:
            if f.exists():
                with contextlib.suppress(OSError):
                    f.unlink()

    return results


async def render_diagram(diagram_code: str, output_path: Path) -> bool:
    """
    渲染单个 Mermaid 图表

    基于 render_diagrams 的便捷封装。
    """
    results = await render_diagrams([(diagram_code, output_path)])
    return results[0] if results else False


def get_diagnostic_message() -> str:
    """返回渲染器状态诊断信息（用于日志/前端提示）"""
    parts: list[str] = []

    js = _load_mermaid_js()
    if js:
        parts.append(f"✓ mermaid.js ({len(js)} bytes)")
    else:
        parts.append("✗ mermaid.min.js 未找到")

    from app.core.browser_check import chromium_manager

    if chromium_manager.check():
        parts.append("✓ Chromium 已安装")
    else:
        parts.append("✗ Chromium 未安装")

    return " | ".join(parts)
