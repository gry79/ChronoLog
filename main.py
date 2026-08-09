#!/usr/bin/env python3
"""ChronoLog – time tracking application entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path when started as script
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import load_config
from app.db.connection import Database
from app.logger import log
from app.web import create_app, init_database


ASCII_ART = r"""
   ____  _                         _                 _
  / ___| |__  _ __ ___  _ __   ___| |    ___   __ _  | |
 | |   | '_ \| '__/ _ \| '_ \ / _ \ |   / _ \ / _` | | |
 | |___| | | | | | (_) | | | | (_) | |__| (_) | (_| | |_|
  \____|_| |_|_|  \___/|_| |_|\___/|_____\___/ \__, | (_)
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
    try:
        init_database(db)
        app = create_app(config, db)
        log.info("Starting ChronoLog on port %s", config.web_port)
        # host 0.0.0.0 for Docker; debug off for production safety
        app.run(host="0.0.0.0", port=config.web_port, debug=False, threaded=True)
    except KeyboardInterrupt:
        log.info("Shutting down (KeyboardInterrupt)")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
