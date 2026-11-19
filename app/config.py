"""Application configuration loaded from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.logger import log


@dataclass
class AppConfig:
    db_file: str = "chronolog.db"
    allow_user_registration: bool = False
    session_timeout_idle_min: int = 120
    session_timeout_hard_min: int = 600
    web_port: int = 8080
    config_path: str = "config.yaml"

    @property
    def db_path(self) -> Path:
        return Path(self.db_file).expanduser().resolve()


def load_config(config_path: str | Path) -> AppConfig:
    """Load configuration from a YAML file. Missing keys use defaults."""
    path = Path(config_path).expanduser().resolve()
    cfg = AppConfig(config_path=str(path))

    if not path.is_file():
        log.warning("Config file not found at %s – using defaults", path)
        return cfg

    with path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh) or {}

    if "db_file" in data:
        cfg.db_file = str(data["db_file"])
    if "allow_user_registration" in data:
        cfg.allow_user_registration = _as_bool(data["allow_user_registration"])
    if "session_timeout_idle_min" in data:
        cfg.session_timeout_idle_min = _as_int(
            data["session_timeout_idle_min"], "session_timeout_idle_min", 1, 100000
        )
    if "session_timeout_hard_min" in data:
        cfg.session_timeout_hard_min = _as_int(
            data["session_timeout_hard_min"], "session_timeout_hard_min", 1, 100000
        )
    if "web_port" in data:
        cfg.web_port = _as_int(data["web_port"], "web_port", 1, 65535)

    # Resolve relative db_file against config file directory
    db = Path(cfg.db_file)
    if not db.is_absolute():
        cfg.db_file = str((path.parent / db).resolve())

    if cfg.session_timeout_idle_min > cfg.session_timeout_hard_min:
        raise ValueError("session_timeout_idle_min cannot exceed session_timeout_hard_min")

    log.info("Configuration loaded from %s", path)
    return cfg


def _as_bool(value: Any) -> bool:
    """Parse a YAML boolean. The string \"false\" must not become True."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def _as_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid integer for {name}: {value!r}") from exc
    if not (minimum <= number <= maximum):
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return number
