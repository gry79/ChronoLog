"""Time parsing, duration, and calendar helpers."""

from __future__ import annotations

import calendar
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
