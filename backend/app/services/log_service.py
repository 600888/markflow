"""日志服务：内存环形缓冲区存储日志，通过 loguru sink 自动采集。"""

import threading
from collections import deque
from datetime import datetime

from loguru import logger

MAX_LOG_ENTRIES = 500


class LogEntry:
    """单条日志。"""

    def __init__(self, level: str, message: str, source: str = "") -> None:
        self.timestamp = datetime.now(datetime.UTC).isoformat(sep=" ", timespec="seconds")
        self.level = level  # INFO / WARN / ERROR
        self.message = message
        self.source = source

    def to_dict(self) -> dict:
        """将日志条目转为字典。"""
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "source": self.source,
        }


class LogService:
    """内存环形缓冲区日志服务，线程安全。"""

    def __init__(self, max_entries: int = MAX_LOG_ENTRIES) -> None:
        self._max = max_entries
        self._lock = threading.Lock()
        self._logs: deque[LogEntry] = deque(maxlen=max_entries)

    def add(self, level: str, message: str, source: str = "") -> None:
        """添加一条日志。"""
        with self._lock:
            self._logs.append(LogEntry(level, message, source))

    def info(self, message: str, source: str = "") -> None:
        """记录 INFO 级别日志。"""
        self.add("INFO", message, source)

    def warn(self, message: str, source: str = "") -> None:
        """记录 WARN 级别日志。"""
        self.add("WARN", message, source)

    def error(self, message: str, source: str = "") -> None:
        """记录 ERROR 级别日志。"""
        self.add("ERROR", message, source)

    def get_logs(
        self,
        level: str | None = None,
        search: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """获取日志条目列表，支持按级别和关键词过滤。"""
        with self._lock:
            entries = list(self._logs)

        if level and level.upper() != "ALL":
            entries = [e for e in entries if e.level == level.upper()]
        if search:
            q = search.lower()
            entries = [e for e in entries if q in e.message.lower()]

        # 按时间倒序返回最新的 limit 条
        entries.reverse()
        return [e.to_dict() for e in entries[:limit]]

    def clear(self) -> None:
        """清空所有日志。"""
        with self._lock:
            self._logs.clear()

    def count(self) -> int:
        """返回日志条目数量。"""
        with self._lock:
            return len(self._logs)


def install_loguru_sink(log_service: LogService) -> int:
    """
    向 loguru 注册一个 sink，捕获所有模块的日志到 LogService。

    返回 sink id，可用于后续移除。
    """

    def sink_func(message) -> None:
        record = message.record
        level = "INFO"
        if record["level"].name in ("ERROR", "CRITICAL", "EXCEPTION"):
            level = "ERROR"
        elif record["level"].name == "WARNING":
            level = "WARN"

        source = record["extra"].get("task", record["name"] or "")
        msg = record["message"]
        log_service.add(level, msg, source)

    return logger.add(
        sink_func,
        level="DEBUG",
        format="{message}",  # 我们已从 record 中取 message，此格式不影响
    )
