"""Tests for authentication and configuration fixes."""

from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from app.config import load_config
from app.security import generate_csrf_token, generate_token, hash_token
from app.services.time_utils import now_local
from tests.support import ChronoTest


class ConfigTests(unittest.TestCase):
    def test_string_false_stays_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(
                'allow_user_registration: "false"\n'
                "session_timeout_idle_min: 10\n"
                "session_timeout_hard_min: 20\n"
                "web_port: 8080\n",
                encoding="utf-8",
            )
            cfg = load_config(path)
            self.assertFalse(cfg.allow_user_registration)
            self.assertEqual(cfg.web_port, 8080)

    def test_invalid_port_and_timeout_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text("web_port: 0\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)
            path.write_text(
                "session_timeout_idle_min: 600\n"
                "session_timeout_hard_min: 120\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_config(path)


class AuthHardeningTests(ChronoTest):
    def test_session_id_is_stored_hashed(self) -> None:
        self.register()
        cookie = self.client.get_cookie("chronolog_session")
        self.assertIsNotNone(cookie)
        raw = cookie.value
        row = self.db.fetchone("SELECT id FROM sessions")
        self.assertEqual(row[0], hash_token(raw))
        self.assertNotEqual(row[0], raw)

    def test_legacy_plaintext_session_still_works(self) -> None:
        self.register()
        token = generate_token(32)
        self.db.execute(
            """
            INSERT INTO sessions (id, user_id, expires_hard, csrf_token)
            VALUES (?, 1, ?, ?)
            """,
            [token, now_local() + timedelta(hours=1), generate_csrf_token()],
        )
        self.client.set_cookie("chronolog_session", token)
        response = self.client.get("/time")
        self.assertEqual(response.status_code, 200)
        upgraded = self.db.fetchone(
            "SELECT id FROM sessions WHERE id = ?",
            [hash_token(token)],
        )
        self.assertIsNotNone(upgraded)

    def test_long_password_is_rejected(self) -> None:
        password = "a" * 72 + "1"
        response = self.client.post(
            "/register",
            data={
                "username": "bob",
                "first_name": "Bob",
                "last_name": "Builder",
                "email": "bob@example.com",
                "password": password,
                "password_repeat": password,
            },
        )
        self.assertIn("72 Bytes", response.get_data(as_text=True))
        self.assertIsNone(self.app.config["USERS"].get_by_username("bob"))

    def test_unknown_user_gets_generic_login_error(self) -> None:
        response = self.client.post(
            "/login",
            data={"username": "nobody", "password": "secret1"},
        )
        self.assertIn("Ungültige Login Daten", response.get_data(as_text=True))

    def test_password_change_ends_the_session(self) -> None:
        self.register()
        token = self.csrf("/settings")
        response = self.client.post(
            "/settings",
            data={
                "csrf_token": token,
                "action": "password",
                "current_password": "secret1",
                "new_password": "secret2",
                "new_password_repeat": "secret2",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
        follow = self.client.get("/time", follow_redirects=False)
        self.assertEqual(follow.status_code, 302)

    def test_logout_requires_post_and_csrf(self) -> None:
        self.register()
        self.assertEqual(self.client.get("/logout").status_code, 405)
        self.assertEqual(self.client.post("/logout").status_code, 400)
        self.assertEqual(self.client.get("/time").status_code, 200)
        token = self.csrf()
        response = self.client.post("/logout", data={"csrf_token": token})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
