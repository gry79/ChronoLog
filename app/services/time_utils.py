"""Time parsing, duration, and calendar helpers."""

from __future__ import annotations

import calendar
import math
import re
from datetime import date, datetime, timedelta
from typing import Optional

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_DIGITS_RE = re.compile(r"^\d{3,4}$")


def parse_time_input(value: str) -> Optional[str]:
    """
    Parse flexible time input into 'hh:mm'.
    Accepts: '08:00', '8:00', '800', '8', '0800'.
    Returns None if empty; raises ValueError if invalid.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if raw == "":
        return None

    raw = raw.replace(".", ":").replace(",", ":")

    if _DIGITS_RE.match(raw):
        if len(raw) == 3:
            h, m = int(raw[0]), int(raw[1:])
        else:
            h, m = int(raw[:2]), int(raw[2:])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError(f"Invalid time: {value}")
        return f"{h:02d}:{m:02d}"

    if re.match(r"^\d{1,2}$", raw):
        h = int(raw)
        if not (0 <= h <= 23):
            raise ValueError(f"Invalid time: {value}")
        return f"{h:02d}:00"

    m = _TIME_RE.match(raw)
    if not m:
        raise ValueError(f"Invalid time format: {value}")
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise ValueError(f"Invalid time: {value}")
    return f"{h:02d}:{mi:02d}"


def time_to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def duration_hours(time_from: Optional[str], time_to: Optional[str]) -> float:
    """Return duration in decimal hours. Incomplete pairs return 0."""
    if not time_from or not time_to:
        return 0.0
    start = time_to_minutes(time_from)
    end = time_to_minutes(time_to)
    if end <= start:
        return 0.0
    return round((end - start) / 60.0, 2)


def intervals_overlap(a_from: str, a_to: str, b_from: str, b_to: str) -> bool:
    a0, a1 = time_to_minutes(a_from), time_to_minutes(a_to)
    b0, b1 = time_to_minutes(b_from), time_to_minutes(b_to)
    return a0 < b1 and b0 < a1


def month_days(year: int, month: int) -> list[date]:
    n = calendar.monthrange(year, month)[1]
    return [date(year, month, d) for d in range(1, n + 1)]


def prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def month_label_de(year: int, month: int) -> str:
    names = [
        "Januar", "Februar", "März", "April", "Mai", "Juni",
        "Juli", "August", "September", "Oktober", "November", "Dezember",
    ]
    return f"{names[month - 1]} {year}"


def weekday_name_de(d: date) -> str:
    names = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    return names[d.weekday()]


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def format_hours(h: float) -> str:
    return f"{h:.1f}" if abs(h - round(h)) > 0.05 else f"{h:.1f}"


def daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def now_local() -> datetime:
    return datetime.now()


def parse_decimal(value: str) -> float:
    """Parse a decimal entered with a dot or comma. Rejects NaN and infinity."""
    number = float(str(value).strip().replace(",", "."))
    if not math.isfinite(number):
        raise ValueError(f"Not a finite number: {value}")
    return number


def is_real_calendar_day(month: int, day: int, year: Optional[int]) -> bool:
    """True for a real date. Recurring days (no year) may be 29 February."""
    if not (1 <= month <= 12):
        return False
    if year is not None:
        try:
            date(int(year), month, day)
            return True
        except (ValueError, OverflowError):
            return False
    if month == 2:
        return 1 <= day <= 29
    return 1 <= day <= calendar.monthrange(2001, month)[1]


def effective_start(
    start_year: Optional[int],
    start_month: Optional[int],
    today: Optional[date] = None,
) -> tuple[int, int]:
    """Start month for a user. Invalid stored values fall back to today."""
    today = today or date.today()
    year = start_year if isinstance(start_year, int) else today.year
    month = start_month if isinstance(start_month, int) else today.month
    if not (1970 <= year <= 2100):
        year = today.year
    if not (1 <= month <= 12):
        month = today.month
    return year, month


def validate_month_view(
    year: int,
    month: int,
    start: tuple[int, int],
    today: Optional[date] = None,
) -> Optional[str]:
    """Error text when a month is not a valid, reachable time-entry month."""
    today = today or date.today()
    if not isinstance(year, int) or not isinstance(month, int):
        return "Ungültiger Monat"
    if not (1970 <= year <= 2100 and 1 <= month <= 12):
        return "Ungültiger Monat"
    if (year, month) < start or (year, month) > (today.year, today.month):
        return "Monat liegt ausserhalb des erlaubten Bereichs"
    return None
