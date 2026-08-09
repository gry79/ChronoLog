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
        cfg.allow_user_registration = bool(data["allow_user_registration"])
    if "session_timeout_idle_min" in data:
        cfg.session_timeout_idle_min = int(data["session_timeout_idle_min"])
    if "session_timeout_hard_min" in data:
        cfg.session_timeout_hard_min = int(data["session_timeout_hard_min"])
    if "web_port" in data:
        cfg.web_port = int(data["web_port"])

    # Resolve relative db_file against config file directory
    db = Path(cfg.db_file)
    if not db.is_absolute():
        cfg.db_file = str((path.parent / db).resolve())

    log.info("Configuration loaded from %s", path)
    return cfg
