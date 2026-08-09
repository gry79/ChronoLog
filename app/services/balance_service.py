"""Time account (Zeitkonto) calculations."""

from __future__ import annotations

from datetime import date
from typing import Optional

from app.db.repositories import (
    AbsenceRepository,
    Chronos,
    MonthClosureRepository,
    TimeEntryRepository,
    User,
)
from app.services.chronos_service import ChronosService
from app.services.time_utils import (
    duration_hours,
    daterange,
    next_month,
)


class BalanceService:
    def __init__(
        self,
        time_repo: TimeEntryRepository,
        absence_repo: AbsenceRepository,
        month_repo: MonthClosureRepository,
        chronos_service: ChronosService,
    ) -> None:
        self.time_repo = time_repo
        self.absence_repo = absence_repo
        self.month_repo = month_repo
        self.chronos_service = chronos_service

    def worked_hours_for_month(
        self, user_id: int, year: int, month: int, chronos: Optional[Chronos]
    ) -> float:
        """Sum of time-entry durations + absence hours attributed to the month."""
        entries = self.time_repo.list_for_month(user_id, year, month)
        total = sum(duration_hours(e.time_from, e.time_to) for e in entries)

        absences = self.absence_repo.list_for_month(user_id, year, month)
        for ab in absences:
            total += self._absence_hours_in_month(ab, year, month, chronos)
        return round(total, 2)

    def _absence_hours_in_month(
        self, ab, year: int, month: int, chronos: Optional[Chronos]
    ) -> float:
        if ab.date_from == ab.date_to:
            # Partial or full single day – only count if that day is in the month
            if ab.date_from.year == year and ab.date_from.month == month:
                if ab.hours is not None:
                    return float(ab.hours)
                if chronos:
                    return self.chronos_service.target_for_date(chronos, ab.date_from)
                return 0.0
            return 0.0

        # Multi-day: each day in range gets that day's soll (within the month)
        total = 0.0
        for d in daterange(ab.date_from, ab.date_to):
            if d.year == year and d.month == month:
                if chronos:
                    total += self.chronos_service.target_for_date(chronos, d)
        return total

    def start_year_month(self, user: User) -> tuple[int, int]:
        today = date.today()
        y = user.start_year if user.start_year else today.year
        m = user.start_month if user.start_month else today.month
        return y, m

    def carried_balance(
        self, user: User, year: int, month: int, chronos: Optional[Chronos]
    ) -> float:
        """
        Zeitkonto Vormonat for the given month view.
        At start month: initial_balance.
        Otherwise: previous month's ending balance.
        """
        sy, sm = self.start_year_month(user)
        if (year, month) == (sy, sm):
            return round(float(user.initial_balance), 2)

        # Walk from start month to the month before (year, month)
        bal = float(user.initial_balance)
        cy, cm = sy, sm
        while (cy, cm) != (year, month):
            monthly_target = (
                self.chronos_service.monthly_target(chronos, cy, cm) if chronos else 0.0
            )
            worked = self.worked_hours_for_month(user.id, cy, cm, chronos)
            bal = bal - monthly_target + worked
            cy, cm = next_month(cy, cm)
            # Safety against infinite loop
            if cy > year + 1:
                break
        return round(bal, 2)

    def current_balance(
        self, user: User, year: int, month: int, chronos: Optional[Chronos]
    ) -> float:
        carried = self.carried_balance(user, year, month, chronos)
        monthly_target = (
            self.chronos_service.monthly_target(chronos, year, month) if chronos else 0.0
        )
        worked = self.worked_hours_for_month(user.id, year, month, chronos)
        return round(carried - monthly_target + worked, 2)

    def day_worked_hours(self, user_id: int, d: date) -> float:
        entries = self.time_repo.list_for_date(user_id, d)
        return round(sum(duration_hours(e.time_from, e.time_to) for e in entries), 2)
