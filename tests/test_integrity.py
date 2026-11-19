"""Tests for data-integrity bugs in ChronoLog."""

from __future__ import annotations

import os
import threading
import time
from datetime import date, datetime

from app.db import migrations
from app.services.time_utils import month_days, prev_month
from tests.support import ChronoTest


class TransactionTests(ChronoTest):
    def test_rollback_discards_insert(self) -> None:
        self.db.execute("CREATE TABLE rollback_probe (id INTEGER)")
        self.db.execute("INSERT INTO rollback_probe VALUES (1)")
        with self.assertRaises(RuntimeError):
            with self.db.transaction():
                self.db.execute("INSERT INTO rollback_probe VALUES (2)")
                raise RuntimeError("boom")
        count = self.db.fetchone("SELECT COUNT(*) FROM rollback_probe")
        self.assertEqual(int(count[0]), 1)

    def test_transaction_lock_blocks_other_threads(self) -> None:
        self.db.execute("CREATE TABLE lock_probe (id INTEGER)")
        in_txn = threading.Event()
        release = threading.Event()

        def writer() -> None:
            with self.db.transaction():
                self.db.execute("INSERT INTO lock_probe VALUES (1)")
                in_txn.set()
                release.wait(3)

        thread = threading.Thread(target=writer)
        thread.start()
        self.addCleanup(lambda: release.set())
        self.assertTrue(in_txn.wait(2))

        reader = threading.Thread(
            target=lambda: self.db.fetchone("SELECT COUNT(*) FROM lock_probe")
        )
        reader.start()
        time.sleep(0.2)
        self.assertTrue(reader.is_alive(), "reader ran inside the open transaction")
        release.set()
        reader.join(2)
        thread.join(2)
        self.assertFalse(reader.is_alive())
        count = self.db.fetchone("SELECT COUNT(*) FROM lock_probe")
        self.assertEqual(int(count[0]), 1)

    def test_failed_migration_is_not_recorded(self) -> None:
        original = list(migrations.MIGRATIONS)
        migrations.MIGRATIONS = original + [
            (99, "bad", ["SELECT * FROM table_that_does_not_exist_zzz"])
        ]
        try:
            with self.assertRaises(RuntimeError):
                migrations.run_migrations(self.db)
            row = self.db.fetchone("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")
            self.assertEqual(int(row[0]), 2)
        finally:
            migrations.MIGRATIONS = original

    def test_repeated_fetchone_keeps_the_connection_usable(self) -> None:
        first = self.db.fetchone("SELECT 1")
        second = self.db.fetchone("SELECT 2")
        self.assertEqual(int(first[0]), 1)
        self.assertEqual(int(second[0]), 2)


class SessionClockTests(ChronoTest):
    def test_last_activity_uses_local_clock(self) -> None:
        previous = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/Zurich"
        time.tzset()
        try:
            self.register()
            row = self.db.fetchone("SELECT last_activity FROM sessions")
            self.assertIsNotNone(row)
            stored = row[0]
            if getattr(stored, "tzinfo", None) is not None:
                stored = stored.replace(tzinfo=None)
            delta = abs((stored - datetime.now()).total_seconds())
            self.assertLess(delta, 5)
        finally:
            if previous is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = previous
            time.tzset()


class MonthAndAbsenceTests(ChronoTest):
    def setUp(self) -> None:
        super().setUp()
        self.register()
        self.user = self.app.config["USERS"].get_by_id(1)
        self.chronos = self.app.config["CHRONOS_REPO"].create("Standard", 8.0)
        self.app.config["USERS"].update_profile(
            self.user.id,
            self.user.username,
            self.user.first_name,
            self.user.last_name,
            chronos_id=self.chronos.id,
            start_year=date.today().year - 2,
            start_month=1,
            initial_balance=2.5,
        )
        self.user = self.app.config["USERS"].get_by_id(1)

    def test_invalid_month_does_not_crash(self) -> None:
        token = self.csrf()
        response = self.post_form(
            "/time/save",
            [
                ("csrf_token", token),
                ("year", "2026"),
                ("month", "13"),
            ],
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ungültiger Monat", response.get_data(as_text=True))

    def test_overlapping_times_are_rejected(self) -> None:
        day = _weekday_in_month(date.today().year, date.today().month)
        token = self.csrf()
        response = self.post_form(
            "/time/save",
            [
                ("csrf_token", token),
                ("year", str(day.year)),
                ("month", str(day.month)),
                ("entry_date", day.isoformat()),
                ("entry_date", day.isoformat()),
                ("time_from", "08:00"),
                ("time_from", "09:00"),
                ("time_to", "12:00"),
                ("time_to", "10:00"),
                ("description", ""),
                ("description", ""),
                ("sort_order", "0"),
                ("sort_order", "1"),
            ],
        )
        self.assertIn("Überlappende Zeiten", response.get_data(as_text=True))

    def test_absence_cannot_leave_the_month_or_use_nan(self) -> None:
        today = date.today()
        service = self.app.config["ABSENCE_SVC"]
        next_month = date(today.year + (today.month == 12), 1 if today.month == 12 else today.month + 1, 1)
        error = service.save_for_month(
            self.user,
            today.year,
            today.month,
            [{"date_from": today.isoformat(), "date_to": next_month.isoformat(), "hours": "", "description": ""}],
        )
        self.assertIn("Enddatum", error or "")

        day = _weekday_in_month(today.year, today.month)
        error = service.save_for_month(
            self.user,
            day.year,
            day.month,
            [{"date_from": day.isoformat(), "date_to": day.isoformat(), "hours": "nan", "description": ""}],
        )
        self.assertEqual(error, "Ungültiger Stundenwert")

        error = service.save_for_month(
            self.user,
            day.year,
            day.month,
            [{"date_from": day.isoformat(), "date_to": day.isoformat(), "hours": "2,5", "description": "Arzt"}],
        )
        self.assertIsNone(error)
        worked = self.app.config["BALANCE_SVC"].worked_hours_for_month(
            self.user.id, day.year, day.month, self.chronos
        )
        self.assertEqual(worked, 2.5)

    def test_absence_overlaps_entry_from_another_month(self) -> None:
        today = date.today()
        day = _weekday_in_month(today.year, today.month)
        previous_year, previous_month = prev_month(today.year, today.month)
        self.db.execute(
            """
            INSERT INTO absences (id, user_id, date_from, date_to, hours, description)
            VALUES (1, ?, ?, ?, NULL, 'alt')
            """,
            [self.user.id, date(previous_year, previous_month, 1), day],
        )
        error = self.app.config["ABSENCE_SVC"].save_for_month(
            self.user,
            day.year,
            day.month,
            [{"date_from": day.isoformat(), "date_to": day.isoformat(), "hours": "1", "description": "neu"}],
        )
        self.assertEqual(error, "Absenzen dürfen sich nicht überlappen")

    def test_balance_and_special_day_override(self) -> None:
        repo = self.app.config["CHRONOS_REPO"]
        svc = self.app.config["CHRONOS_SVC"]
        repo.add_special_day(self.chronos.id, 1, 1, None, 0, "Neujahr")
        manual = 0.0
        for day in month_days(2026, 1):
            if (day.month, day.day) == (1, 1) or day.weekday() >= 5:
                continue
            manual += 8
        self.assertEqual(svc.monthly_target(self.chronos, 2026, 1), manual)
        repo.add_special_day(self.chronos.id, 1, 1, 2026, 4, "Halbtag")
        self.assertEqual(svc.target_for_date(self.chronos, date(2026, 1, 1)), 4.0)
        self.assertEqual(svc.target_for_date(self.chronos, date(2027, 1, 1)), 0.0)

        today = date.today()
        self.app.config["USERS"].update_profile(
            self.user.id,
            self.user.username,
            self.user.first_name,
            self.user.last_name,
            chronos_id=self.chronos.id,
            start_year=today.year,
            start_month=today.month,
            initial_balance=2.5,
        )
        user = self.app.config["USERS"].get_by_id(1)
        with self.app.test_request_context("/time"):
            view = self.app.config["TIME_SVC"].build_month_view(user, today.year, today.month)
        self.assertEqual(view.carried_balance, 2.5)
        self.assertEqual(view.current_balance, round(2.5 - view.monthly_target + view.worked_hours, 2))

    def test_specials_are_not_queried_once_per_day(self) -> None:
        repo = self.app.config["CHRONOS_REPO"]
        calls = {"n": 0}
        original = repo.list_special_days

        def wrapped(chronos_id: int):
            calls["n"] += 1
            return original(chronos_id)

        repo.list_special_days = wrapped
        today = date.today()
        user = self.app.config["USERS"].get_by_id(1)
        with self.app.test_request_context("/time"):
            self.app.config["TIME_SVC"].build_month_view(user, today.year, today.month)
        # One lookup per year from the start year through today, not per day.
        self.assertLess(calls["n"], 8)

    def test_invalid_special_day_is_not_stored(self) -> None:
        token = self.csrf("/admin/chronos")
        response = self.post_form(
            "/admin/chronos/save",
            [
                ("csrf_token", token),
                ("name", "Kaputt"),
                ("daily_target_hours", "nan"),
            ],
        )
        self.assertIn("Ungültige Soll-Arbeitszeit", response.get_data(as_text=True))
        names = [item.name for item in self.app.config["CHRONOS_REPO"].list_all()]
        self.assertNotIn("Kaputt", names)

        token = self.csrf("/admin/chronos")
        response = self.post_form(
            "/admin/chronos/save",
            [
                ("csrf_token", token),
                ("name", "Februar"),
                ("daily_target_hours", "8,0"),
                ("sd_month", "2"),
                ("sd_day", "31"),
                ("sd_year", ""),
                ("sd_target", "0"),
                ("sd_description", "gibt es nicht"),
            ],
        )
        self.assertIn("Monat/Tag ungültig", response.get_data(as_text=True))
        names = [item.name for item in self.app.config["CHRONOS_REPO"].list_all()]
        self.assertNotIn("Februar", names)

    def test_admin_cannot_lock_self_or_set_month_13(self) -> None:
        token = self.csrf("/admin/users/edit/1")
        response = self.post_form(
            "/admin/users/save",
            [
                ("csrf_token", token),
                ("user_id", "1"),
                ("username", "ada"),
                ("first_name", "Ada"),
                ("last_name", "Lovelace"),
                ("email", "ada@example.com"),
                ("is_admin", "on"),
                ("is_locked", "on"),
                ("start_month", "13"),
                ("start_year", "2020"),
                ("initial_balance", "0"),
            ],
        )
        text = response.get_data(as_text=True)
        self.assertIn("nicht sperren", text)
        user = self.app.config["USERS"].get_by_id(1)
        self.assertFalse(user.is_locked)

        token = self.csrf("/admin/users/edit/1")
        response = self.post_form(
            "/admin/users/save",
            [
                ("csrf_token", token),
                ("user_id", "1"),
                ("username", "ada"),
                ("first_name", "Ada"),
                ("last_name", "Lovelace"),
                ("email", "ada@example.com"),
                ("is_admin", "on"),
                ("start_month", "13"),
                ("start_year", "2020"),
                ("initial_balance", "0"),
            ],
        )
        self.assertIn("Startmonat", response.get_data(as_text=True))
        user = self.app.config["USERS"].get_by_id(1)
        self.assertNotEqual(user.start_month, 13)

    def test_invalid_start_month_does_not_crash_the_grid(self) -> None:
        self.app.config["USERS"].update_profile(
            1,
            "ada",
            "Ada",
            "Lovelace",
            chronos_id=self.chronos.id,
            start_year=2020,
            start_month=13,
            initial_balance=0,
        )
        response = self.client.get("/time")
        self.assertEqual(response.status_code, 200)

    def test_closed_month_rejects_save(self) -> None:
        today = date.today()
        self.app.config["TIME_SVC"].set_month_closed(self.user, today.year, today.month, True)
        day = _weekday_in_month(today.year, today.month)
        token = self.csrf(f"/time?year={today.year}&month={today.month}")
        response = self.post_form(
            "/time/save",
            [
                ("csrf_token", token),
                ("year", str(today.year)),
                ("month", str(today.month)),
                ("entry_date", day.isoformat()),
                ("time_from", "08:00"),
                ("time_to", "12:00"),
                ("description", ""),
                ("sort_order", "0"),
            ],
        )
        self.assertIn("abgeschlossen", response.get_data(as_text=True))


def _weekday_in_month(year: int, month: int) -> date:
    for day in month_days(year, month):
        if day.weekday() < 5:
            return day
    raise AssertionError(f"no weekday in {year}-{month}")
