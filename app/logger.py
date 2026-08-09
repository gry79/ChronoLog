"""Colored console logging for ChronoLog."""

from __future__ import annotations

import logging
import re
import sys
from typing import Optional


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
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _use_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class ColoredFormatter(logging.Formatter):
    """Format: yyyy-mm-dd hh:mm:ss SEVERITY message (with optional color)."""

    def __init__(self, use_color: bool) -> None:
        super().__init__(fmt="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        # Work on a copy so we don't mutate the original record for other handlers
        record = logging.makeLogRecord(record.__dict__)
        record.msg = strip_ansi(str(record.getMessage()))
        record.args = ()

        asctime = self.formatTime(record, self.datefmt)
        level = record.levelname
        message = record.getMessage()

        # Prefix every line (Werkzeug sometimes emits multi-line messages)
        lines = message.splitlines() or [""]
        out: list[str] = []
        for line in lines:
            line = line.strip()
            if line.startswith("* "):
                line = line[2:]
            if self.use_color:
                sev_color = _SEVERITY_COLORS.get(record.levelno, "")
                out.append(
                    f"{_DARK_ORANGE}{asctime}{_RESET} {sev_color}{level}{_RESET} {line}"
                )
            else:
                out.append(f"{asctime} {level} {line}")
        return "\n".join(out)


def _make_handler(level: int = logging.INFO) -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(ColoredFormatter(use_color=_use_color()))
    return handler


def setup_logger(name: str = "chronolog", level: int = logging.INFO) -> logging.Logger:
    """Create and return the application logger (idempotent)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False
    logger.addHandler(_make_handler(level))
    return logger


def configure_web_loggers(level: int = logging.INFO) -> None:
    """
    Route Flask / Werkzeug log output through the same format as ChronoLog.
    Call once before app.run().
    """
    for name in ("werkzeug", "flask", "flask.app"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.setLevel(level)
        logger.propagate = False
        logger.addHandler(_make_handler(level))

    # Flask click-based banner → our logger
    try:
        import flask.cli as flask_cli

        def _banner(debug: bool, app_import_path: Optional[str]) -> None:
            if app_import_path is not None:
                log.info("Serving Flask app %r", app_import_path)
            log.info("Debug mode: %s", "on" if debug else "off")

        flask_cli.show_server_banner = _banner  # type: ignore[assignment]
    except Exception:
        pass

    # Werkzeug multi-line startup → separate clean log lines
    try:
        import socket

        from werkzeug.serving import BaseWSGIServer, get_interface_ip

        def _log_startup(self) -> None:  # type: ignore[no-untyped-def]
            log.warning(
                "This is a development server. Do not use it in a production "
                "deployment. Use a production WSGI server instead."
            )
            if getattr(self, "address_family", None) is not None:
                # af_unix path
                import socket as _socket

                if self.address_family == getattr(_socket, "AF_UNIX", object()):
                    log.info("Running on %s", self.host)
                    return

            scheme = "http" if self.ssl_context is None else "https"
            display_hostname = self.host

            if self.host in {"0.0.0.0", "::"}:
                log.info("Running on all addresses (%s)", self.host)
                if self.host == "0.0.0.0":
                    localhost = "127.0.0.1"
                    try:
                        display_hostname = get_interface_ip(socket.AF_INET)
                    except Exception:
                        display_hostname = "127.0.0.1"
                else:
                    localhost = "[::1]"
                    try:
                        display_hostname = get_interface_ip(socket.AF_INET6)
                    except Exception:
                        display_hostname = "::1"
                log.info("Running on %s://%s:%s", scheme, localhost, self.port)

            if ":" in str(display_hostname) and not str(display_hostname).startswith("["):
                display_hostname = f"[{display_hostname}]"

            log.info("Running on %s://%s:%s", scheme, display_hostname, self.port)

        BaseWSGIServer.log_startup = _log_startup  # type: ignore[method-assign]
    except Exception:
        pass


log = setup_logger()
