"""从 Pandoc 默认样式生成 reference.docx（脚本工具，非运行时依赖）"""

from __future__ import annotations

import subprocess
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# 各模版对应的生成参数
TEMPLATE_CONFIG = {
    "minimal": None,  # 使用 Pandoc 默认样式
    "academic": None,
    "report": None,
}


def run() -> None:
    for slug, _cfg in TEMPLATE_CONFIG.items():
        template_dir = TEMPLATES_DIR / slug
        ref_path = template_dir / "reference.docx"

        if ref_path.exists():
            print(f"[跳过] {slug}/reference.docx 已存在")
            continue

        # 用 Pandoc 从空 Markdown 生成 reference.docx
        md_path = template_dir / "_tmp.md"
        md_path.write_text("# Title\n\nBody text.\n")

        subprocess.run(
            [
                "pandoc",
                str(md_path),
                "-o",
                str(ref_path),
            ],
            check=True,
        )
        md_path.unlink()
        print(f"[生成] {slug}/reference.docx")

    print("完成")


if __name__ == "__main__":
    run()
