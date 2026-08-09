"""Werkzeug request handler using ChronoLog's logger format."""

from __future__ import annotations

from werkzeug.serving import WSGIRequestHandler

from app.logger import log, strip_ansi


class ChronoLogRequestHandler(WSGIRequestHandler):
    """HTTP access log without Werkzeug's nested timestamp style."""

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        try:
            from werkzeug.urls import uri_to_iri

            path = uri_to_iri(self.path)
            req = f"{self.command} {path} {self.request_version}"
        except Exception:
            req = self.requestline

        req = strip_ansi(req.translate(self._control_char_table))
        log.info('%s "%s" %s %s', self.address_string(), req, code, size)

    def log(self, type: str, message: str, *args) -> None:  # type: ignore[override]
        """Route any remaining handler logs through the app logger."""
        msg = (message % args) if args else message
        msg = strip_ansi(msg.rstrip("\n"))
        # Drop Werkzeug's embedded date stamp if a parent path still calls log()
        level = type if type in ("debug", "info", "warning", "error") else "info"
        getattr(log, level)("%s", msg)
