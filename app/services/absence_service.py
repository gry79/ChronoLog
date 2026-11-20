"""Absence entry business logic."""

from __future__ import annotations

from datetime import date
from typing import Optional

from app.db.repositories import AbsenceRepository, TimeEntryRepository, User
from app.logger import log
from app.services.chronos_service import ChronosService
from app.services.time_utils import (
    daterange,
    duration_hours,
    effective_start,
    parse_decimal,
    validate_month_view,
)


def _mark_absence(row: dict, message: str, *more: dict) -> str:
    """Attach a validation message to the submitted row and return it."""
    row["error"] = message
    for extra in more:
        extra["error"] = message
    return message


class AbsenceService:
    def __init__(
        self,
        absence_repo: AbsenceRepository,
        time_repo: TimeEntryRepository,
        chronos_service: ChronosService,
    ) -> None:
        self.absence_repo = absence_repo
        self.time_repo = time_repo
        self.chronos_service = chronos_service

    def list_for_month(self, user: User, year: int, month: int) -> list[dict]:
        absences = self.absence_repo.list_for_month(user.id, year, month)
        result = []
        for a in absences:
            result.append(
                {
                    "id": a.id,
                    "date_from": a.date_from.isoformat(),
                    "date_to": a.date_to.isoformat(),
                    "date_from_display": a.date_from.strftime("%d.%m.%Y"),
                    "date_to_display": a.date_to.strftime("%d.%m.%Y"),
                    "hours": a.hours if a.hours is not None else "",
                    "description": a.description,
                    "error": "",
                }
            )
        return result

    def save_for_month(
        self, user: User, year: int, month: int, raw_rows: list[dict]
    ) -> Optional[str]:
        window = validate_month_view(
            year, month, effective_start(user.start_year, user.start_month)
        )
        if window:
            return window
        chronos = self.chronos_service.get_for_user(user)
        if not chronos:
            return "Bitte zuerst eine Chronos-Konfiguration in den Einstellungen wählen"

        parsed: list[dict] = []
        for row in raw_rows:
            df_raw = (row.get("date_from") or "").strip()
            dt_raw = (row.get("date_to") or "").strip()
            if not df_raw and not dt_raw:
                continue
            try:
                df = date.fromisoformat(df_raw)
                dt = date.fromisoformat(dt_raw or df_raw)
            except ValueError:
                return _mark_absence(row, "Ungültiges Datumsformat")

            if df.year != year or df.month != month:
                return _mark_absence(row, "Das Startdatum muss im gewählten Monat liegen")
            if dt.year != year or dt.month != month:
                return _mark_absence(row, "Das Enddatum muss im gewählten Monat liegen")
            if dt < df:
                return _mark_absence(row, "Enddatum muss am oder nach dem Startdatum liegen")

            hours_raw = row.get("hours")
            hours: Optional[float] = None
            if df == dt:
                if hours_raw not in (None, ""):
                    try:
                        hours = parse_decimal(str(hours_raw))
                    except ValueError:
                        return _mark_absence(row, "Ungültiger Stundenwert")
                    if hours < 0:
                        return _mark_absence(row, "Stunden dürfen nicht negativ sein")
            else:
                hours = None  # multi-day: auto soll per day

            desc = (row.get("description") or "")[:256]

            # Validation against time entries and daily target
            err = self._validate_absence(user.id, df, dt, hours, chronos)
            if err:
                return _mark_absence(row, err)

            parsed.append(
                {
                    "user_id": user.id,
                    "date_from": df,
                    "date_to": dt,
                    "hours": hours,
                    "description": desc,
                    "_src": row,
                }
            )

        # Overlap between absences themselves
        for i, a in enumerate(parsed):
            for b in parsed[i + 1 :]:
                if a["date_from"] <= b["date_to"] and b["date_from"] <= a["date_to"]:
                    return _mark_absence(
                        b["_src"], "Absenzen dürfen sich nicht überlappen", a["_src"]
                    )

        # Rows stored under another month (date_from outside this month) are kept.
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1)
        else:
            month_end = date(year, month + 1, 1)
        replaced_ids = {
            item.id
            for item in self.absence_repo.list_all_for_user(user.id)
            if month_start <= item.date_from < month_end
        }
        for item in parsed:
            if self.absence_repo.has_overlap_with_dates(
                user.id, item["date_from"], item["date_to"], replaced_ids
            ):
                return _mark_absence(item["_src"], "Absenzen dürfen sich nicht überlappen")

        try:
            self.absence_repo.replace_for_month(user.id, year, month, parsed)
        except Exception:
            log.exception("Failed to save absences for user=%s %04d-%02d", user.id, year, month)
            return (
                "Speichern fehlgeschlagen (Datenbankfehler). "
                "Bitte Seite neu laden und erneut versuchen."
            )
        log.info(
            "Saved absences for user=%s %04d-%02d (%s rows)",
            user.id,
            year,
            month,
            len(parsed),
        )
        return None

    def _validate_absence(self, user_id, df, dt, hours, chronos) -> Optional[str]:
        if df == dt:
            target = self.chronos_service.target_for_date(chronos, df)
            worked = sum(
                duration_hours(e.time_from, e.time_to)
                for e in self.time_repo.list_for_date(user_id, df)
            )
            abs_h = hours if hours is not None else target
            if round(worked + abs_h, 2) > round(target, 2):
                return (
                    f"Am {df.strftime('%d.%m.%Y')}: Zeiteinträge ({worked:.1f}h) + "
                    f"Absenz ({abs_h:.1f}h) überschreiten die Soll-Arbeitszeit ({target:.1f}h)"
                )
            return None

        # Multi-day: no time entries allowed in range
        for d in daterange(df, dt):
            entries = self.time_repo.list_for_date(user_id, d)
            if any(e.time_from and e.time_to for e in entries):
                return (
                    f"Mehrtägige Absenz nicht möglich: Zeiteinträge am "
                    f"{d.strftime('%d.%m.%Y')} vorhanden"
                )
        return None
