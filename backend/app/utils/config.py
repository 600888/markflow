"""应用配置管理 - 基于 Pydantic Settings，支持环境变量覆盖"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

from config.paths import DATA_DIR


class AppSettings(BaseSettings):
    """全局应用配置"""

    # 服务
    host: str = "127.0.0.1"
    port: int = 62581
    debug: bool = False

    # Pandoc
    pandoc_path: str | None = None
    pandoc_timeout: int = 300

    # Word 转 PDF
    microsoft_word_path: Path | None = None
    wps_path: Path | None = None
    word_conversion_timeout: int = 180

    # 文件
    max_file_size: int = 50 * 1024 * 1024
    temp_dir: Path = Path("temp")
    output_dir: Path = Path("output")
    data_dir: Path = DATA_DIR

    # 并发
    max_concurrent_tasks: int = 4
    max_concurrent_word_tasks: int = 2

    # 日志
    log_level: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_prefix": "MARKFLOW_",
        "case_sensitive": False,
    }
