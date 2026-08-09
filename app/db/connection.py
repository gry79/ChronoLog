"""Thread-safe DuckDB connection wrapper."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional, Sequence

import duckdb

from app.logger import log


class Database:
    """Single-file DuckDB access with a write lock for web concurrency."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._conn: Optional[duckdb.DuckDBPyConnection] = None

    def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.db_path.exists()
        self._conn = duckdb.connect(str(self.db_path))
        if is_new:
            log.info("Created new database at %s", self.db_path)
        else:
            log.info("Opened database at %s", self.db_path)

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
                log.info("Database connection closed")

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> duckdb.DuckDBPyConnection:
        with self._lock:
            if params is None:
                return self.conn.execute(sql)
            return self.conn.execute(sql, list(params))

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple]:
        with self._lock:
            cur = self.execute(sql, params)
            return cur.fetchall()

    def fetchone(self, sql: str, params: Sequence[Any] | None = None) -> Optional[tuple]:
        with self._lock:
            cur = self.execute(sql, params)
            return cur.fetchone()

    def executemany(self, sql: str, params_seq: Sequence[Sequence[Any]]) -> None:
        with self._lock:
            self.conn.executemany(sql, list(params_seq))
