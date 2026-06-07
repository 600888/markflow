"""Services 模块日志"""

from __future__ import annotations

from app.utils.logger import Log
from config.paths import LOG_DIR

log = Log(
    filename=str(LOG_DIR / "services.log"),
    cmdlevel="DEBUG",
    filelevel="INFO",
    limit=2048000,
    backup_count=1,
    colorful=True,
    enqueue=True,
)
