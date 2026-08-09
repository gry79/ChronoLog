"""Colored console logging for ChronoLog."""

from __future__ import annotations

import logging
import sys


# ANSI colors (only applied when stdout is a TTY)
_DARK_ORANGE = "\033[38;5;208m"
_RESET = "\033[0m"
_SEVERITY_COLORS = {
    logging.DEBUG: "\033[36m",     # cyan
    logging.INFO: "\033[32m",      # green
    logging.WARNING: "\033[33m",   # yellow
    logging.ERROR: "\033[31m",     # red
    logging.CRITICAL: "\033[35m",  # magenta
}


class ColoredFormatter(logging.Formatter):
    """Format: yyyy-mm-dd hh:mm:ss SEVERITY message (with optional color)."""

    def __init__(self, use_color: bool) -> None:
        super().__init__(fmt="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        raw = super().format(record)
        if not self.use_color:
            return raw

        # Split into date-time, severity, message
        # asctime is "yyyy-mm-dd hh:mm:ss" (19 chars)
        asctime = raw[:19]
        rest = raw[20:]
        level = record.levelname
        # rest starts with levelname + space + message
        message = rest[len(level) + 1 :] if rest.startswith(level) else rest
        sev_color = _SEVERITY_COLORS.get(record.levelno, "")
        return f"{_DARK_ORANGE}{asctime}{_RESET} {sev_color}{level}{_RESET} {message}"


def setup_logger(name: str = "chronolog", level: int = logging.INFO) -> logging.Logger:
    """Create and return the application logger (idempotent)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    use_color = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    handler.setFormatter(ColoredFormatter(use_color=use_color))
    logger.addHandler(handler)
    return logger


log = setup_logger()
