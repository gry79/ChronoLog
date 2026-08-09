"""Chronos target-hour calculations."""

from __future__ import annotations

from datetime import date
from typing import Optional

from app.db.repositories import Chronos, ChronosRepository, SpecialDay, User
from app.services.time_utils import is_weekend, month_days


class ChronosService:
    def __init__(self, chronos_repo: ChronosRepository) -> None:
        self.repo = chronos_repo

    def get_for_user(self, user: User) -> Optional[Chronos]:
        if not user.chronos_id:
            return None
        return self.repo.get(user.chronos_id)

    def special_days_map(
        self, chronos_id: int, year: int
    ) -> dict[tuple[int, int], SpecialDay]:
        """
        Map (month, day) -> SpecialDay for a year.
        Year-specific entries override recurring ones.
        """
        days = self.repo.list_special_days(chronos_id)
        recurring: dict[tuple[int, int], SpecialDay] = {}
        specific: dict[tuple[int, int], SpecialDay] = {}
        for sd in days:
            key = (sd.month, sd.day)
            if sd.year is None:
                recurring[key] = sd
            elif sd.year == year:
                specific[key] = sd
        result = dict(recurring)
        result.update(specific)
        return result

    def target_for_date(self, chronos: Chronos, d: date) -> float:
        """Soll hours for a calendar day."""
        specials = self.special_days_map(chronos.id, d.year)
        key = (d.month, d.day)
        if key in specials:
            return float(specials[key].target_hours)
        if is_weekend(d):
            return 0.0
        return float(chronos.daily_target_hours)

    def monthly_target(self, chronos: Chronos, year: int, month: int) -> float:
        total = 0.0
        for d in month_days(year, month):
            total += self.target_for_date(chronos, d)
        return round(total, 2)

    @staticmethod
    def is_zero_hours(hours: float) -> bool:
        return abs(float(hours)) < 1e-9

    def is_free_day(self, chronos: Optional[Chronos], d: date) -> bool:
        """
        Days that are hidden by default in the time-entry grid:
        weekends and Chronos special days (or any day) with 0.0 soll hours.
        Same treatment as Saturday/Sunday for navigation arrows.
        """
        if chronos is None:
            return is_weekend(d)
        return self.is_zero_hours(self.target_for_date(chronos, d))

    def is_hidden_by_default(self, chronos: Optional[Chronos], d: date) -> bool:
        """Alias for is_free_day (weekends + 0.0h special days)."""
        return self.is_free_day(chronos, d)
