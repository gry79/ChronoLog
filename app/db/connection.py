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

    def reconnect(self) -> None:
        """Close and reopen the connection (e.g. after a FatalException)."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
            self._conn = duckdb.connect(str(self.db_path))
            log.warning("Reconnected to database at %s", self.db_path)

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

    def _is_fatal(self, exc: BaseException) -> bool:
        name = type(exc).__name__
        return name == "FatalException" or "FatalException" in name

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> duckdb.DuckDBPyConnection:
        with self._lock:
            try:
                if params is None:
                    return self.conn.execute(sql)
                return self.conn.execute(sql, list(params))
            except Exception as exc:
                if self._is_fatal(exc):
                    log.error("DuckDB fatal error on execute – reconnecting: %s", exc)
                    self.reconnect()
                raise

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple]:
        with self._lock:
            try:
                cur = self.conn.execute(sql) if params is None else self.conn.execute(sql, list(params))
                return cur.fetchall()
            except Exception as exc:
                if self._is_fatal(exc):
                    log.error("DuckDB fatal error on fetchall – reconnecting: %s", exc)
                    self.reconnect()
                raise

    def fetchone(self, sql: str, params: Sequence[Any] | None = None) -> Optional[tuple]:
        with self._lock:
            try:
                cur = self.conn.execute(sql) if params is None else self.conn.execute(sql, list(params))
                return cur.fetchone()
            except Exception as exc:
                if self._is_fatal(exc):
                    log.error("DuckDB fatal error on fetchone – reconnecting: %s", exc)
                    self.reconnect()
                raise

    def executemany(self, sql: str, params_seq: Sequence[Sequence[Any]]) -> None:
        with self._lock:
            try:
                self.conn.executemany(sql, list(params_seq))
            except Exception as exc:
                if self._is_fatal(exc):
                    log.error("DuckDB fatal error on executemany – reconnecting: %s", exc)
                    self.reconnect()
                raise

    def begin(self) -> None:
        self.execute("BEGIN TRANSACTION")

    def commit(self) -> None:
        self.execute("COMMIT")

    def rollback(self) -> None:
        try:
            self.execute("ROLLBACK")
        except Exception:
            # Connection may already be dead; reconnect leaves a clean session
            try:
                self.reconnect()
            except Exception:
                pass
