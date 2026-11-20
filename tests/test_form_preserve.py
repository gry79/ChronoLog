"""Submitted values stay on the form when validation fails."""

from __future__ import annotations

from datetime import date

from app.services.time_utils import month_days, next_month
from tests.support import ChronoTest


def _weekday(year: int, month: int) -> date:
    for day in month_days(year, month):
        if day.weekday() < 5:
            return day
    raise AssertionError(f"no weekday in {year}-{month}")


class FormPreserveTests(ChronoTest):
    def test_duplicate_special_days_keep_every_row(self) -> None:
        self.register()
        token = self.csrf("/admin/chronos")
        response = self.post_form(
            "/admin/chronos/save",
            [
                ("csrf_token", token),
                ("name", "Zürich"),
                ("daily_target_hours", "8,4"),
                ("sd_day", "25"),
                ("sd_month", "12"),
                ("sd_year", ""),
                ("sd_target", "0"),
                ("sd_description", "Weihnachten"),
                ("sd_day", "25"),
                ("sd_month", "12"),
                ("sd_year", ""),
                ("sd_target", "0"),
                ("sd_description", "Weihnachten nochmal"),
                ("sd_day", "6"),
                ("sd_month", "4"),
                ("sd_year", ""),
                ("sd_target", "4.2"),
                ("sd_description", "Sechseläuten"),
            ],
        )
        text = response.get_data(as_text=True)
        self.assertIn("doppelt erfasst", text)
        self.assertIn("Weihnachten nochmal", text)
        self.assertIn("Sechseläuten", text)
        self.assertIn("8,4", text)
        self.assertIsNone(
            next((item for item in self.app.config["CHRONOS_REPO"].list_all() if item.name == "Zürich"), None)
        )

    def test_time_entry_overlap_keeps_both_rows(self) -> None:
        self.register()
        day = _weekday(date.today().year, date.today().month)
        token = self.csrf(f"/time?year={day.year}&month={day.month}")
        response = self.post_form(
            "/time/save",
            [
                ("csrf_token", token),
                ("year", str(day.year)),
                ("month", str(day.month)),
                ("entry_date", day.isoformat()),
                ("entry_date", day.isoformat()),
                ("time_from", "08:00"),
                ("time_from", "09:30"),
                ("time_to", "12:00"),
                ("time_to", "11:00"),
                ("description", "Morgen"),
                ("description", "Überlappung"),
                ("sort_order", "0"),
                ("sort_order", "1"),
            ],
        )
        text = response.get_data(as_text=True)
        self.assertIn("Überlappende Zeiten", text)
        self.assertIn("08:00", text)
        self.assertIn("09:30", text)
        self.assertIn("Überlappung", text)
        stored = self.app.config["TIME_SVC"].time_repo.list_for_date(1, day)
        self.assertFalse(any(entry.time_from == "09:30" for entry in stored))

    def test_absence_error_keeps_all_rows(self) -> None:
        self.register()
        user = self.app.config["USERS"].get_by_id(1)
        chronos = self.app.config["CHRONOS_REPO"].create("Standard", 8.0)
        self.app.config["USERS"].update_profile(
            user.id, user.username, user.first_name, user.last_name, chronos_id=chronos.id
        )
        today = date.today()
        ny, nm = next_month(today.year, today.month)
        token = self.csrf(f"/absences?year={today.year}&month={today.month}")
        response = self.post_form(
            "/absences/save",
            [
                ("csrf_token", token),
                ("year", str(today.year)),
                ("month", str(today.month)),
                ("date_from", today.isoformat()),
                ("date_to", date(ny, nm, 1).isoformat()),
                ("hours", ""),
                ("description", "Zu lang"),
                ("date_from", today.isoformat()),
                ("date_to", today.isoformat()),
                ("hours", "2,5"),
                ("description", "Arzt"),
            ],
        )
        text = response.get_data(as_text=True)
        self.assertIn("Enddatum", text)
        self.assertIn("Zu lang", text)
        self.assertIn("Arzt", text)
        self.assertIn("2,5", text)
        self.assertEqual(self.app.config["ABSENCE_SVC"].absence_repo.list_all_for_user(1), [])

    def test_settings_keep_invalid_profile_input(self) -> None:
        self.register()
        token = self.csrf("/settings")
        response = self.post_form(
            "/settings",
            [
                ("csrf_token", token),
                ("action", "profile"),
                ("username", "ada-neu"),
                ("first_name", "Augusta"),
                ("last_name", "King"),
                ("chronos_id", ""),
                ("start_year", "2024"),
                ("start_month", "13"),
                ("initial_balance", "1,5"),
            ],
        )
        text = response.get_data(as_text=True)
        self.assertIn("Startmonat", text)
        self.assertIn("ada-neu", text)
        self.assertIn("Augusta", text)
        self.assertIn("1,5", text)
        user = self.app.config["USERS"].get_by_id(1)
        self.assertEqual(user.username, "ada")
        self.assertEqual(user.first_name, "Ada")
        self.assertNotEqual(user.start_month, 13)

    def test_register_keeps_text_fields_and_drops_password(self) -> None:
        response = self.client.post(
            "/register",
            data={
                "username": "bob",
                "first_name": "Bob",
                "last_name": "Builder",
                "email": "bob@example.com",
                "password": "abcdef",
                "password_repeat": "abcdef",
            },
        )
        text = response.get_data(as_text=True)
        self.assertIn("bob@example.com", text)
        self.assertIn('value="bob"', text)
        self.assertIn("Zahl", text)
        self.assertNotIn("abcdef", text)
        self.assertIsNone(self.app.config["USERS"].get_by_username("bob"))

    def test_login_keeps_username(self) -> None:
        self.register()
        token = self.csrf()
        self.client.post("/logout", data={"csrf_token": token})
        response = self.client.post("/login", data={"username": "ada", "password": "wrong1"})
        text = response.get_data(as_text=True)
        self.assertIn('value="ada"', text)
        self.assertIn("Ungültige Login Daten", text)
        self.assertNotIn("wrong1", text)

    def test_admin_create_keeps_fields_and_drops_password(self) -> None:
        self.register()
        token = self.csrf("/admin/users")
        response = self.post_form(
            "/admin/users/create",
            [
                ("csrf_token", token),
                ("username", "carla"),
                ("first_name", "Carla"),
                ("last_name", "Muster"),
                ("email", "carla@example.com"),
                ("password", "abcdef"),
            ],
        )
        text = response.get_data(as_text=True)
        self.assertIn("carla@example.com", text)
        self.assertIn("Zahl", text)
        self.assertNotIn("abcdef", text)
        self.assertIsNone(self.app.config["USERS"].get_by_username("carla"))
