"""Access control, session cookies, headers and login rate limiting."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import load_config
from app.db.connection import Database
from app.services.time_utils import month_days
from app.web import create_app, init_database
from app.web.rate_limit import AttemptLimiter
from tests.support import ChronoTest


def _weekday(year: int, month: int) -> date:
    for day in month_days(year, month):
        if day.weekday() < 5:
            return day
    raise AssertionError(f"no weekday in {year}-{month}")


class AccessAndSessionTests(ChronoTest):
    def test_security_headers_on_anonymous_page(self) -> None:
        response = self.client.get("/login")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("object-src 'none'", response.headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotIn("Strict-Transport-Security", response.headers)

    def test_login_replaces_preexisting_cookie(self) -> None:
        self.register()
        token = self.csrf()
        self.client.post("/logout", data={"csrf_token": token})
        self.client.set_cookie("chronolog_session", "attacker-token")
        response = self.client.post(
            "/login",
            data={"username": "ada", "password": "secret1"},
        )
        header = response.headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", header)
        self.assertIn("SameSite=Lax", header)
        self.assertNotIn("Secure", header)
        cookie = self.client.get_cookie("chronolog_session")
        self.assertIsNotNone(cookie)
        self.assertNotEqual(cookie.value, "attacker-token")
        self.assertEqual(response.status_code, 302)

    def test_user_cannot_read_or_edit_another_users_time(self) -> None:
        self.register()
        token = self.csrf("/admin/users")
        created = self.post_form(
            "/admin/users/create",
            [
                ("csrf_token", token),
                ("username", "bob"),
                ("first_name", "Bob"),
                ("last_name", "Builder"),
                ("email", "bob@example.com"),
                ("password", "secret1"),
            ],
        )
        self.assertEqual(created.status_code, 200)
        self.assertIsNotNone(self.app.config["USERS"].get_by_username("bob"))

        day = _weekday(date.today().year, date.today().month)
        ada_token = self.csrf(f"/time?year={day.year}&month={day.month}")
        self.post_form(
            "/time/save",
            [
                ("csrf_token", ada_token),
                ("year", str(day.year)),
                ("month", str(day.month)),
                ("entry_date", day.isoformat()),
                ("time_from", "08:00"),
                ("time_to", "09:00"),
                ("description", "nur-ada"),
                ("sort_order", "0"),
            ],
        )

        bob = self.app.test_client()
        bob.post("/login", data={"username": "bob", "password": "secret1"})
        bob_page = bob.get(f"/time?year={day.year}&month={day.month}")
        self.assertNotIn("nur-ada", bob_page.get_data(as_text=True))
        self.assertEqual(bob.get("/admin/chronos").status_code, 403)
        self.assertEqual(bob.post("/admin/chronos/save", data={"name": "fremd"}).status_code, 403)

        bob_token = self._csrf(bob, f"/time?year={day.year}&month={day.month}")
        bob.post(
            "/time/save",
            data={
                "csrf_token": bob_token,
                "year": str(day.year),
                "month": str(day.month),
                "entry_date": day.isoformat(),
                "time_from": "10:00",
                "time_to": "11:00",
                "description": "nur-bob",
                "sort_order": "0",
            },
        )
        ada_page = self.client.get(f"/time?year={day.year}&month={day.month}")
        self.assertIn("nur-ada", ada_page.get_data(as_text=True))
        self.assertNotIn("nur-bob", ada_page.get_data(as_text=True))

    def test_login_rate_limit_keeps_username_and_skips_further_checks(self) -> None:
        self.register()
        token = self.csrf()
        self.client.post("/logout", data={"csrf_token": token})
        self.app.config["LOGIN_LIMIT"] = AttemptLimiter(per_name=3, per_ip=3, window_seconds=900)
        for _ in range(3):
            self.client.post("/login", data={"username": "ada", "password": "wrong1"})
        blocked = self.client.post("/login", data={"username": "ada", "password": "secret1"})
        text = blocked.get_data(as_text=True)
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Zu viele Anmeldeversuche", text)
        self.assertIn('value="ada"', text)
        self.assertNotIn("secret1", text)

    @staticmethod
    def _csrf(client, path: str) -> str:
        import re

        html = client.get(path).get_data(as_text=True)
        match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        assert match is not None
        return match.group(1)


class ProxyConfigTests(ChronoTest):
    def test_trust_proxy_is_off_unless_configured(self) -> None:
        self.assertNotIsInstance(self.app.wsgi_app, ProxyFix)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text('trust_proxy: "true"\nweb_port: 8080\n', encoding="utf-8")
            loaded = load_config(path)
            self.assertTrue(loaded.trust_proxy)
            db_path = Path(tmp) / "extra.db"
            loaded.db_file = str(db_path)
            database = Database(loaded.db_path)
            database.connect()
            self.addCleanup(database.close)
            init_database(database)
            proxied = create_app(loaded, database)
            self.assertIsInstance(proxied.wsgi_app, ProxyFix)
