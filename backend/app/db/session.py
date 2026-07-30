"""SQLite 引擎和会话管理。"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.engine import create_engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    """应用级 SQLite 数据库。"""

    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self.path = (data_dir / "markflow.sqlite3").resolve()
        self.engine = create_engine(
            f"sqlite:///{self.path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        event.listen(self.engine, "connect", _configure_sqlite)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
        )

    def initialize(self) -> None:
        """执行 Alembic 迁移，把数据库升级到最新版本。"""
        config = Config()
        config.set_main_option("script_location", str(_migration_directory()))
        config.set_main_option("sqlalchemy.url", f"sqlite:///{self.path.as_posix()}")
        command.upgrade(config, "head")

    def close(self) -> None:
        """关闭数据库连接池。"""
        self.engine.dispose()


def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def _migration_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "migrations"  # type: ignore[attr-defined]  # noqa: SLF001
    return Path(__file__).resolve().parents[2] / "migrations"
