"""集成测试：将 data/ 下所有 Markdown 文件转换为 Word"""

from __future__ import annotations

import shutil

import pytest

from app.core.engine import PandocEngine
from app.models import OutputFormat
from config.paths import DATA_DIR

OUTPUT_DIR = DATA_DIR / "word"


@pytest.mark.skipif(
    not DATA_DIR.exists(),
    reason=f"data 目录不存在: {DATA_DIR}",
)
@pytest.mark.integration
class TestMdToWordConversion:
    """真实 Pandoc 转换测试"""

    @pytest.fixture(scope="class")
    def engine(self) -> PandocEngine:
        return PandocEngine()

    def test_data_dir_has_md_files(self) -> None:
        """确保 data/ 目录下存在 Markdown 文件"""
        files = list(DATA_DIR.glob("*.md"))
        assert len(files) > 0, f"data/ 下没有 .md 文件: {DATA_DIR}"

    @pytest.mark.asyncio
    async def test_convert_all_md_to_word(
        self,
        engine: PandocEngine,
    ) -> None:
        """将所有 .md 文件转换为 .docx 并输出到 word/ 目录"""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        md_files = sorted(DATA_DIR.glob("*.md"))
        assert len(md_files) > 0

        results = []

        for md_file in md_files:
            output_file = OUTPUT_DIR / f"{md_file.stem}.docx"

            result = await engine.convert(
                input_path=md_file,
                output_format=OutputFormat.DOCX,
                extra_args=["--from=gfm"],
            )

            assert result.file_size > 0
            assert result.duration_ms > 0

            shutil.copy2(result.output_path, output_file)
            assert output_file.exists()

            results.append((md_file.name, output_file.name, result.duration_ms, result.file_size))

        # 打印汇总
        print(f"\n{'='*60}")
        print(f"共转换 {len(results)} 个文件到 {OUTPUT_DIR}")
        for name, out, ms, size in results:
            print(f"  ✅ {name} → {out}  ({ms}ms, {size} bytes)")
        print(f"{'='*60}")
