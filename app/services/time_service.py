"""Time entry business logic and month grid building."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.db.repositories import (
    Chronos,
    MonthClosureRepository,
    TimeEntry,
    TimeEntryRepository,
    User,
)
from app.logger import log
from app.services.balance_service import BalanceService
from app.services.chronos_service import ChronosService
from app.services.time_utils import (
    duration_hours,
    intervals_overlap,
    is_weekend,
    month_days,
    month_label_de,
    next_month,
    parse_time_input,
    weekday_name_de,
)


@dataclass
class DayRow:
    entry_date: date
    date_label: str
    weekday: str
    target_hours: float
    is_special: bool
    is_expanded_zero: bool  # shown even though target is 0
    entries: list[dict] = field(default_factory=list)
    day_total: float = 0.0
    special_description: str = ""


@dataclass
class MonthView:
    year: int
    month: int
    label: str
    is_closed: bool
    can_go_prev: bool
    can_go_next: bool
    daily_target: float
    monthly_target: float
    carried_balance: float
    current_balance: float
    worked_hours: float
    days: list[DayRow]
    user_display_name: str


class TimeService:
    def __init__(
        self,
        time_repo: TimeEntryRepository,
        month_repo: MonthClosureRepository,
        chronos_service: ChronosService,
        balance_service: BalanceService,
    ) -> None:
        self.time_repo = time_repo
        self.month_repo = month_repo
        self.chronos_service = chronos_service
        self.balance_service = balance_service

    def clamp_month(self, user: User, year: int, month: int) -> tuple[int, int]:
        today = date.today()
        sy, sm = self.balance_service.start_year_month(user)
        # Not before start
        if (year, month) < (sy, sm):
            year, month = sy, sm
        # Not after current month
        if (year, month) > (today.year, today.month):
            year, month = today.year, today.month
        return year, month

    def can_navigate_next(self, user: User, year: int, month: int) -> bool:
        today = date.today()
        ny, nm = next_month(year, month)
        if (ny, nm) > (today.year, today.month):
            return False
        # May only advance if current month is closed
        return self.month_repo.is_closed(user.id, year, month)

    def build_month_view(
        self,
        user: User,
        year: int,
        month: int,
        expand_dates: Optional[set[date]] = None,
    ) -> MonthView:
        year, month = self.clamp_month(user, year, month)
        chronos = self.chronos_service.get_for_user(user)
        entries = self.time_repo.list_for_month(user.id, year, month)

        by_date: dict[date, list[TimeEntry]] = {}
        for e in entries:
            by_date.setdefault(e.entry_date, []).append(e)

        expand = expand_dates or set()
        # Auto-expand days that already have stored entries but would be hidden
        for d in by_date:
            expand.add(d)

        days: list[DayRow] = []
        specials = (
            self.chronos_service.special_days_map(chronos.id, year) if chronos else {}
        )

        for d in month_days(year, month):
            target = (
                self.chronos_service.target_for_date(chronos, d) if chronos else (0.0 if is_weekend(d) else 8.0)
            )
            hidden = target == 0.0
            if hidden and d not in expand:
                continue

            day_entries = by_date.get(d, [])
            entry_dicts: list[dict] = []
            running = 0.0
            if not day_entries:
                entry_dicts.append(
                    {
                        "id": None,
                        "time_from": "",
                        "time_to": "",
                        "description": "",
                        "total": 0.0,
                        "sort_order": 0,
                    }
                )
            else:
                for e in day_entries:
                    dur = duration_hours(e.time_from, e.time_to)
                    running += dur
                    entry_dicts.append(
                        {
                            "id": e.id,
                            "time_from": e.time_from or "",
                            "time_to": e.time_to or "",
                            "description": e.description or "",
                            "total": round(running, 2),
                            "sort_order": e.sort_order,
                        }
                    )

            special = specials.get((d.month, d.day)) if chronos else None
            days.append(
                DayRow(
                    entry_date=d,
                    date_label=d.strftime("%d.%m.%Y"),
                    weekday=weekday_name_de(d),
                    target_hours=target,
                    is_special=special is not None,
                    is_expanded_zero=hidden,
                    entries=entry_dicts,
                    day_total=round(running if day_entries else 0.0, 2),
                    special_description=(special.description or "").strip() if special else "",
                )
            )

        # Annotate show_up / show_down / can_delete per entry
        self._annotate_actions(days, year, month, chronos)

        sy, sm = self.balance_service.start_year_month(user)
        can_prev = (year, month) > (sy, sm)
        can_next = self.can_navigate_next(user, year, month)

        return MonthView(
            year=year,
            month=month,
            label=month_label_de(year, month),
            is_closed=self.month_repo.is_closed(user.id, year, month),
            can_go_prev=can_prev,
            can_go_next=can_next,
            daily_target=float(chronos.daily_target_hours) if chronos else 0.0,
            monthly_target=(
                self.chronos_service.monthly_target(chronos, year, month) if chronos else 0.0
            ),
            carried_balance=self.balance_service.carried_balance(user, year, month, chronos),
            current_balance=self.balance_service.current_balance(user, year, month, chronos),
            worked_hours=self.balance_service.worked_hours_for_month(
                user.id, year, month, chronos
            ),
            days=days,
            user_display_name=f"{user.last_name}, {user.first_name}",
        )

    def _annotate_actions(
        self, days: list[DayRow], year: int, month: int, chronos: Optional[Chronos]
    ) -> None:
        all_dates = month_days(year, month)
        shown = {d.entry_date for d in days}

        for day in days:
            n = len(day.entries)
            for i, e in enumerate(day.entries):
                e["show_plus"] = True
                e["show_delete"] = not (n == 1 and not day.is_expanded_zero)
                e["show_up"] = False
                e["show_down"] = False

            # Up arrow on first entry if previous calendar day is hidden (weekend/0h)
            if day.entries:
                idx = all_dates.index(day.entry_date)
                if idx > 0:
                    prev_d = all_dates[idx - 1]
                    prev_hidden = (
                        self.chronos_service.is_hidden_by_default(chronos, prev_d)
                        if chronos is not None
                        else is_weekend(prev_d)
                    )
                    if prev_hidden and prev_d not in shown:
                        day.entries[0]["show_up"] = True
                        day.entries[0]["expand_date"] = prev_d.isoformat()

                # Down arrow on last entry if next calendar day is hidden
                if idx < len(all_dates) - 1:
                    next_d = all_dates[idx + 1]
                    next_hidden = (
                        self.chronos_service.is_hidden_by_default(chronos, next_d)
                        if chronos is not None
                        else is_weekend(next_d)
                    )
                    if next_hidden and next_d not in shown:
                        day.entries[-1]["show_down"] = True
                        day.entries[-1]["expand_date"] = next_d.isoformat()

    def save_month_entries(
        self, user: User, year: int, month: int, raw_rows: list[dict]
    ) -> Optional[str]:
        """Validate and replace all entries for the month. Returns error message or None."""
        if self.month_repo.is_closed(user.id, year, month):
            return "Monat ist abgeschlossen und kann nicht bearbeitet werden"

        parsed: list[dict] = []
        by_date: dict[date, list[dict]] = {}

        for row in raw_rows:
            try:
                d = date.fromisoformat(row["entry_date"])
            except (KeyError, ValueError):
                return "Ungültiges Datum in den Formulardaten"
            if d.year != year or d.month != month:
                return "Datum liegt ausserhalb des gewählten Monats"

            try:
                tf = parse_time_input(row.get("time_from") or "")
                tt = parse_time_input(row.get("time_to") or "")
            except ValueError as exc:
                return f"Ungültige Zeitangabe: {exc}"

            desc = (row.get("description") or "")[:256]
            entry = {
                "user_id": user.id,
                "entry_date": d,
                "time_from": tf,
                "time_to": tt,
                "description": desc,
                "sort_order": int(row.get("sort_order") or 0),
                "_has_data": bool(tf or tt or desc),
            }

            if tf and tt and time_to_minutes_safe(tf) >= time_to_minutes_safe(tt):
                return f"Endzeit muss nach Startzeit liegen ({d.strftime('%d.%m.%Y')})"

            by_date.setdefault(d, []).append(entry)

        # Overlap check per day
        for d, items in by_date.items():
            intervals = [
                (it["time_from"], it["time_to"])
                for it in items
                if it["time_from"] and it["time_to"]
            ]
            for i in range(len(intervals)):
                for j in range(i + 1, len(intervals)):
                    a, b = intervals[i], intervals[j]
                    if intervals_overlap(a[0], a[1], b[0], b[1]):
                        return f"Überlappende Zeiten am {d.strftime('%d.%m.%Y')}"

            # Re-number sort_order
            for idx, it in enumerate(items):
                it["sort_order"] = idx
                parsed.append(it)

        # Keep at least one row per non-hidden day; drop pure-empty expanded zero days
        chronos = self.chronos_service.get_for_user(user)
        final: list[dict] = []
        dates_with_rows = set(by_date.keys())

        for d in month_days(year, month):
            items = by_date.get(d, [])
            hidden = self.chronos_service.is_hidden_by_default(chronos, d) if chronos else is_weekend(d)
            if not items:
                if not hidden:
                    final.append(
                        {
                            "user_id": user.id,
                            "entry_date": d,
                            "time_from": None,
                            "time_to": None,
                            "description": "",
                            "sort_order": 0,
                        }
                    )
                continue

            meaningful = [it for it in items if it["_has_data"]]
            if meaningful:
                for it in meaningful:
                    final.append({k: v for k, v in it.items() if not k.startswith("_")})
            elif not hidden:
                final.append(
                    {
                        "user_id": user.id,
                        "entry_date": d,
                        "time_from": None,
                        "time_to": None,
                        "description": "",
                        "sort_order": 0,
                    }
                )
            # else: expanded zero day with no data – drop it

        self.time_repo.delete_for_month(user.id, year, month)
        self.time_repo.insert_batch(final)
        log.info("Saved time entries for user=%s %04d-%02d (%s rows)", user.id, year, month, len(final))
        return None

    def set_month_closed(self, user: User, year: int, month: int, closed: bool) -> None:
        self.month_repo.set_closed(user.id, year, month, closed)
        log.info(
            "Month %04d-%02d %s for user=%s",
            year,
            month,
            "closed" if closed else "reopened",
            user.id,
        )


def time_to_minutes_safe(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)
