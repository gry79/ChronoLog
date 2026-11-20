"""Small in-memory limiter for login and registration attempts."""

from __future__ import annotations

import threading
import time


class AttemptLimiter:
    """Count failures per client address and per account name."""

    def __init__(
        self,
        *,
        per_name: int = 10,
        per_ip: int = 30,
        window_seconds: int = 900,
    ) -> None:
        self.per_name = per_name
        self.per_ip = per_ip
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._events: dict[str, list[float]] = {}

    def is_blocked(self, ip: str, name: str) -> bool:
        now = time.monotonic()
        with self._lock:
            return (
                len(self._prune(now, f"ip:{ip}")) >= self.per_ip
                or len(self._prune(now, f"name:{name}")) >= self.per_name
            )

    def record_failure(self, ip: str, name: str) -> None:
        now = time.monotonic()
        with self._lock:
            for key in (f"ip:{ip}", f"name:{name}"):
                events = self._prune(now, key)
                events.append(now)
                self._events[key] = events

    def record_success(self, name: str) -> None:
        with self._lock:
            self._events.pop(f"name:{name}", None)

    def _prune(self, now: float, key: str) -> list[float]:
        events = [stamp for stamp in self._events.get(key, []) if now - stamp < self.window_seconds]
        if events:
            self._events[key] = events
        else:
            self._events.pop(key, None)
        return events
