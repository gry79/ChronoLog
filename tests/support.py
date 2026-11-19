"""Shared fixtures for ChronoLog tests."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from werkzeug.datastructures import MultiDict

from app.config import load_config
from app.db.connection import Database
from app.web import create_app, init_database


def build_app(tmp: Path):
    db_file = tmp / "chronolog.db"
    cfg = tmp / "config.yaml"
    cfg.write_text(
        f"db_file: {db_file}\n"
        "allow_user_registration: true\n"
        "session_timeout_idle_min: 120\n"
        "session_timeout_hard_min: 600\n"
        "web_port: 8080\n",
        encoding="utf-8",
    )
    config = load_config(cfg)
    db = Database(config.db_path)
    db.connect()
    init_database(db)
    app = create_app(config, db)
    app.config["TESTING"] = True
    return app, db


class ChronoTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.app, self.db = build_app(Path(self._tmp.name))
        self.addCleanup(self.db.close)
        self.client = self.app.test_client()

    def register(self, username: str = "ada") -> None:
        response = self.client.post(
            "/register",
            data={
                "username": username,
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": f"{username}@example.com",
                "password": "secret1",
                "password_repeat": "secret1",
            },
        )
        self.assertEqual(response.status_code, 302)

    def csrf(self, path: str = "/time") -> str:
        html = self.client.get(path).get_data(as_text=True)
        match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        self.assertIsNotNone(match, html[:400])
        return match.group(1)

    def post_form(self, path: str, fields: list[tuple[str, str]]):
        return self.client.post(path, data=MultiDict(fields), follow_redirects=True)
