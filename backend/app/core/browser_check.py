"""
浏览器检测 —— 检查 Microsoft Edge (WebView2) 是否可用

Edge 是 Windows 10+ 自带浏览器，使用其 headless 模式渲染 Mermaid 图表，
无需额外下载 Chromium。

用法:
    from app.core.browser_check import edge_manager

    ok = edge_manager.is_ready()
"""

from __future__ import annotations

import shutil
from pathlib import Path

from app.core.log import log


class EdgeManager:
    """Edge 浏览器检测器"""

    def __init__(self) -> None:
        self._ready: bool | None = None
        self._edge_path: str | None = None

    def _find_edge(self) -> str | None:
        """查找 msedge.exe"""
        if self._edge_path:
            return self._edge_path

        candidates = [
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        ]
        for c in candidates:
            if c.exists():
                self._edge_path = str(c)
                return self._edge_path

        found = shutil.which("msedge")
        if found:
            self._edge_path = found
            return self._edge_path

        return None

    def is_ready(self) -> bool:
        """快速检查 Edge 是否可用"""
        if self._ready is not None:
            return self._ready

        edge = self._find_edge()
        if edge:
            self._ready = True
            log.info(f"Edge 浏览器可用: {edge}")
            return True

        log.warning("未找到 Microsoft Edge，Mermaid 渲染将不可用")
        self._ready = False
        return False

    def check(self) -> bool:
        """同 is_ready"""
        return self.is_ready()

    def executable_path(self) -> str | None:
        """返回 Edge 可执行文件路径，供无头渲染任务使用。"""
        return self._find_edge()

    def get_install_progress(self) -> dict[str, object]:
        """Edge 无需安装，始终返回已就绪或未找到"""
        if self.is_ready():
            return {"progress": 100, "stage": "completed", "message": "Edge 已就绪"}
        return {"progress": 0, "stage": "failed", "message": "未找到 Edge 浏览器"}

    async def ensure(self) -> bool:
        """Edge 无需安装"""
        return self.is_ready()

    def remove(self) -> bool:
        """不支持卸载 Edge"""
        return False


# ── 兼容别名 ────────────────────────────────────────────
# 旧代码用 chromium_manager，保留别名以兼容调用方
edge_manager = EdgeManager()
chromium_manager = edge_manager
