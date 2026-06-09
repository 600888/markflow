"""
CLI 入口：从 template.yaml 自动生成 reference.docx

用法: python scripts/generate_reference.py [slug...]
示例: python scripts/generate_reference.py academic report
      不带参数则生成全部内置模版

内部调用 TemplateGenerator 服务完成实际工作。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 将 backend/ 加入 sys.path，确保 app 包可导入
_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

TEMPLATES_DIR = _BACKEND_DIR / "templates"


def main() -> None:
    from app.services.template_generator import TemplateGenerator

    slugs = sys.argv[1:] if len(sys.argv) > 1 else None
    generator = TemplateGenerator(TEMPLATES_DIR)

    for entry in sorted(TEMPLATES_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith(".") or entry.name == "custom":
            continue
        if slugs and entry.name not in slugs:
            continue
        slug = entry.name
        print(f"[{slug}]")
        ref_bytes = generator.generate_from_yaml(entry)
        if ref_bytes is None:
            print(f"  [WARN] no template.yaml or empty styles, skip {slug}")
            continue
        (entry / "reference.docx").write_bytes(ref_bytes)
        print(f"  [OK] {slug}/reference.docx")

    print("完成")


if __name__ == "__main__":
    main()
