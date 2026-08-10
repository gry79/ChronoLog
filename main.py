#!/usr/bin/env python3
"""ChronoLog – time tracking application entry point."""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from pathlib import Path

# Ensure project root is on sys.path when started as script
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from werkzeug.serving import make_server

from app.config import load_config
from app.db.connection import Database
from app.logger import configure_web_loggers, log
from app.web import create_app, init_database
from app.web.request_log import ChronoLogRequestHandler


# FIGlet "standard" font – ChronoLog (verified column alignment)
ASCII_ART = r"""
  ____ _                           _
 / ___| |__  _ __ ___  _ __   ___ | |    ___   __ _
| |   | '_ \| '__/ _ \| '_ \ / _ \| |   / _ \ / _` |
| |___| | | | | | (_) | | | | (_) | |__| (_) | (_| |
 \____|_| |_|_|  \___/|_| |_|\___/|_____\___/ \__, |
                                              |___/
"""

# Teal-ish color for the banner when TTY supports color
_TEAL = "\033[38;5;37m"
_AMBER = "\033[38;5;214m"
_RESET = "\033[0m"


def print_banner() -> None:
    use_color = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    if use_color:
        print(f"{_TEAL}{ASCII_ART}{_RESET}")
        print(f"  {_AMBER}Time tracking made clear{_RESET}\n")
    else:
        print(ASCII_ART)
        print("  Time tracking made clear\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ChronoLog time tracking application")
    parser.add_argument(
        "-c",
        dest="config",
        default=str(ROOT / "config.yaml"),
        help="Path to config.yaml (default: ./config.yaml)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    print_banner()
    args = parse_args(argv)
    config = load_config(args.config)

    db = Database(config.db_path)
    db.connect()
    httpd = None
    try:
        init_database(db)
        app = create_app(config, db)
        configure_web_loggers()
        log.info("Starting ChronoLog on port %s", config.web_port)

        # make_server + explicit signal handling so Docker SIGTERM stops quickly
        # (app.run() reacts well to Ctrl-C/SIGINT, but not always to SIGTERM).
        httpd = make_server(
            "0.0.0.0",
            config.web_port,
            app,
            threaded=True,
            request_handler=ChronoLogRequestHandler,
        )

        def _request_shutdown(signum: int, _frame) -> None:
            name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
            log.info("Shutting down (%s)", name)
            # shutdown() must not run on the request-handling thread
            threading.Thread(target=httpd.shutdown, daemon=True).start()

        signal.signal(signal.SIGTERM, _request_shutdown)
        signal.signal(signal.SIGINT, _request_shutdown)

        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down (KeyboardInterrupt)")
    finally:
        if httpd is not None:
            try:
                httpd.server_close()
            except Exception:
                pass
        db.close()
        log.info("ChronoLog stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
