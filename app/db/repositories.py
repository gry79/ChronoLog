"""Data access layer for ChronoLog entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

from app.db.connection import Database


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass
class User:
    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    password_hash: str
    is_admin: bool
    is_locked: bool
    chronos_id: Optional[int]
    start_year: Optional[int]
    start_month: Optional[int]
    initial_balance: float
    created_at: Any = None
    updated_at: Any = None


@dataclass
class SessionRow:
    id: str
    user_id: int
    created_at: datetime
    last_activity: datetime
    expires_hard: datetime
    csrf_token: str


@dataclass
class Chronos:
    id: int
    name: str
    daily_target_hours: float


@dataclass
class SpecialDay:
    id: int
    chronos_id: int
    month: int
    day: int
    year: Optional[int]
    target_hours: float
    description: str


@dataclass
class TimeEntry:
    id: int
    user_id: int
    entry_date: date
    time_from: Optional[str]
    time_to: Optional[str]
    description: str
    sort_order: int


@dataclass
class Absence:
    id: int
    user_id: int
    date_from: date
    date_to: date
    hours: Optional[float]
    description: str


def _user_from_row(row: tuple) -> User:
    return User(
        id=row[0],
        username=row[1],
        first_name=row[2],
        last_name=row[3],
        email=row[4],
        password_hash=row[5],
        is_admin=bool(row[6]),
        is_locked=bool(row[7]),
        chronos_id=row[8],
        start_year=row[9],
        start_month=row[10],
        initial_balance=float(row[11] or 0.0),
        created_at=row[12] if len(row) > 12 else None,
        updated_at=row[13] if len(row) > 13 else None,
    )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class UserRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def count(self) -> int:
        row = self.db.fetchone("SELECT COUNT(*) FROM users")
        return int(row[0]) if row else 0

    def get_by_id(self, user_id: int) -> Optional[User]:
        row = self.db.fetchone("SELECT * FROM users WHERE id = ?", [user_id])
        return _user_from_row(row) if row else None

    def get_by_username(self, username: str) -> Optional[User]:
        row = self.db.fetchone(
            "SELECT * FROM users WHERE lower(username) = lower(?)", [username]
        )
        return _user_from_row(row) if row else None

    def list_all(self) -> list[User]:
        rows = self.db.fetchall("SELECT * FROM users ORDER BY last_name, first_name")
        return [_user_from_row(r) for r in rows]

    def create(
        self,
        username: str,
        first_name: str,
        last_name: str,
        email: str,
        password_hash: str,
        is_admin: bool = False,
    ) -> User:
        row = self.db.fetchone("SELECT nextval('users_id_seq')")
        user_id = int(row[0])
        self.db.execute(
            """
            INSERT INTO users (
                id, username, first_name, last_name, email, password_hash, is_admin
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [user_id, username, first_name, last_name, email, password_hash, is_admin],
        )
        user = self.get_by_id(user_id)
        assert user is not None
        return user

    def update_profile(
        self,
        user_id: int,
        username: str,
        first_name: str,
        last_name: str,
        *,
        email: str | None = None,
        chronos_id: Any = ...,
        start_year: Any = ...,
        start_month: Any = ...,
        initial_balance: Any = ...,
        is_admin: Any = ...,
        is_locked: Any = ...,
    ) -> None:
        """Update user fields. Pass ellipsis (...) to leave a field unchanged."""
        user = self.get_by_id(user_id)
        if not user:
            return
        self.db.execute(
            """
            UPDATE users SET
                username = ?,
                first_name = ?,
                last_name = ?,
                email = ?,
                chronos_id = ?,
                start_year = ?,
                start_month = ?,
                initial_balance = ?,
                is_admin = ?,
                is_locked = ?,
                updated_at = current_timestamp
            WHERE id = ?
            """,
            [
                username,
                first_name,
                last_name,
                email if email is not None else user.email,
                user.chronos_id if chronos_id is ... else chronos_id,
                user.start_year if start_year is ... else start_year,
                user.start_month if start_month is ... else start_month,
                user.initial_balance if initial_balance is ... else initial_balance,
                user.is_admin if is_admin is ... else is_admin,
                user.is_locked if is_locked is ... else is_locked,
                user_id,
            ],
        )

    def update_password(self, user_id: int, password_hash: str) -> None:
        self.db.execute(
            """
            UPDATE users SET password_hash = ?, updated_at = current_timestamp
            WHERE id = ?
            """,
            [password_hash, user_id],
        )

    def username_exists(self, username: str, exclude_id: Optional[int] = None) -> bool:
        if exclude_id is None:
            row = self.db.fetchone(
                "SELECT 1 FROM users WHERE lower(username) = lower(?)", [username]
            )
        else:
            row = self.db.fetchone(
                "SELECT 1 FROM users WHERE lower(username) = lower(?) AND id <> ?",
                [username, exclude_id],
            )
        return row is not None


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


class SessionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        session_id: str,
        user_id: int,
        expires_hard: datetime,
        csrf_token: str,
    ) -> None:
        self.db.execute(
            """
            INSERT INTO sessions (id, user_id, expires_hard, csrf_token)
            VALUES (?, ?, ?, ?)
            """,
            [session_id, user_id, expires_hard, csrf_token],
        )

    def get(self, session_id: str) -> Optional[SessionRow]:
        row = self.db.fetchone("SELECT * FROM sessions WHERE id = ?", [session_id])
        if not row:
            return None
        return SessionRow(
            id=row[0],
            user_id=int(row[1]),
            created_at=row[2],
            last_activity=row[3],
            expires_hard=row[4],
            csrf_token=row[5],
        )

    def touch(self, session_id: str) -> None:
        self.db.execute(
            "UPDATE sessions SET last_activity = current_timestamp WHERE id = ?",
            [session_id],
        )

    def delete(self, session_id: str) -> None:
        self.db.execute("DELETE FROM sessions WHERE id = ?", [session_id])

    def delete_for_user(self, user_id: int) -> None:
        self.db.execute("DELETE FROM sessions WHERE user_id = ?", [user_id])

    def delete_expired(self, idle_cutoff: datetime) -> int:
        """Remove sessions past hard expiry or idle timeout."""
        before = self.db.fetchone("SELECT COUNT(*) FROM sessions")
        self.db.execute(
            """
            DELETE FROM sessions
            WHERE expires_hard < current_timestamp
               OR last_activity < ?
            """,
            [idle_cutoff],
        )
        after = self.db.fetchone("SELECT COUNT(*) FROM sessions")
        return int((before[0] if before else 0) - (after[0] if after else 0))


# ---------------------------------------------------------------------------
# Chronos
# ---------------------------------------------------------------------------


class ChronosRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_all(self) -> list[Chronos]:
        rows = self.db.fetchall("SELECT id, name, daily_target_hours FROM chronos ORDER BY name")
        return [Chronos(id=r[0], name=r[1], daily_target_hours=float(r[2])) for r in rows]

    def get(self, chronos_id: int) -> Optional[Chronos]:
        row = self.db.fetchone(
            "SELECT id, name, daily_target_hours FROM chronos WHERE id = ?", [chronos_id]
        )
        if not row:
            return None
        return Chronos(id=row[0], name=row[1], daily_target_hours=float(row[2]))

    def create(self, name: str, daily_target_hours: float) -> Chronos:
        row = self.db.fetchone("SELECT nextval('chronos_id_seq')")
        cid = int(row[0])
        self.db.execute(
            "INSERT INTO chronos (id, name, daily_target_hours) VALUES (?, ?, ?)",
            [cid, name, daily_target_hours],
        )
        return Chronos(id=cid, name=name, daily_target_hours=daily_target_hours)

    def update(self, chronos_id: int, name: str, daily_target_hours: float) -> None:
        self.db.execute(
            """
            UPDATE chronos SET name = ?, daily_target_hours = ?,
                updated_at = current_timestamp WHERE id = ?
            """,
            [name, daily_target_hours, chronos_id],
        )

    def delete(self, chronos_id: int) -> None:
        self.db.execute("DELETE FROM chronos_special_days WHERE chronos_id = ?", [chronos_id])
        self.db.execute("DELETE FROM chronos WHERE id = ?", [chronos_id])

    def list_special_days(self, chronos_id: int) -> list[SpecialDay]:
        rows = self.db.fetchall(
            """
            SELECT id, chronos_id, month, day, year, target_hours, description
            FROM chronos_special_days
            WHERE chronos_id = ?
            ORDER BY month, day, year NULLS LAST
            """,
            [chronos_id],
        )
        return [
            SpecialDay(
                id=r[0],
                chronos_id=r[1],
                month=int(r[2]),
                day=int(r[3]),
                year=int(r[4]) if r[4] is not None else None,
                target_hours=float(r[5]),
                description=r[6] or "",
            )
            for r in rows
        ]

    def add_special_day(
        self,
        chronos_id: int,
        month: int,
        day: int,
        year: Optional[int],
        target_hours: float,
        description: str,
    ) -> SpecialDay:
        row = self.db.fetchone("SELECT nextval('chronos_special_days_id_seq')")
        sid = int(row[0])
        self.db.execute(
            """
            INSERT INTO chronos_special_days
                (id, chronos_id, month, day, year, target_hours, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [sid, chronos_id, month, day, year, target_hours, description],
        )
        return SpecialDay(
            id=sid,
            chronos_id=chronos_id,
            month=month,
            day=day,
            year=year,
            target_hours=target_hours,
            description=description,
        )

    def delete_special_day(self, special_day_id: int) -> None:
        self.db.execute("DELETE FROM chronos_special_days WHERE id = ?", [special_day_id])

    def replace_special_days(self, chronos_id: int, days: list[dict]) -> None:
        self.db.execute("DELETE FROM chronos_special_days WHERE chronos_id = ?", [chronos_id])
        for d in days:
            self.add_special_day(
                chronos_id=chronos_id,
                month=int(d["month"]),
                day=int(d["day"]),
                year=int(d["year"]) if d.get("year") not in (None, "",) else None,
                target_hours=float(d["target_hours"]),
                description=str(d.get("description") or ""),
            )


# ---------------------------------------------------------------------------
# Time entries
# ---------------------------------------------------------------------------


class TimeEntryRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_for_month(self, user_id: int, year: int, month: int) -> list[TimeEntry]:
        rows = self.db.fetchall(
            """
            SELECT id, user_id, entry_date, time_from, time_to, description, sort_order
            FROM time_entries
            WHERE user_id = ?
              AND year(entry_date) = ?
              AND month(entry_date) = ?
            ORDER BY entry_date, sort_order, id
            """,
            [user_id, year, month],
        )
        return [
            TimeEntry(
                id=r[0],
                user_id=r[1],
                entry_date=r[2] if isinstance(r[2], date) else date.fromisoformat(str(r[2])),
                time_from=r[3],
                time_to=r[4],
                description=r[5] or "",
                sort_order=int(r[6]),
            )
            for r in rows
        ]

    def list_for_date(self, user_id: int, entry_date: date) -> list[TimeEntry]:
        rows = self.db.fetchall(
            """
            SELECT id, user_id, entry_date, time_from, time_to, description, sort_order
            FROM time_entries
            WHERE user_id = ? AND entry_date = ?
            ORDER BY sort_order, id
            """,
            [user_id, entry_date],
        )
        return [
            TimeEntry(
                id=r[0],
                user_id=r[1],
                entry_date=r[2] if isinstance(r[2], date) else date.fromisoformat(str(r[2])),
                time_from=r[3],
                time_to=r[4],
                description=r[5] or "",
                sort_order=int(r[6]),
            )
            for r in rows
        ]

    def delete_for_month(self, user_id: int, year: int, month: int) -> None:
        self.db.execute(
            """
            DELETE FROM time_entries
            WHERE user_id = ? AND year(entry_date) = ? AND month(entry_date) = ?
            """,
            [user_id, year, month],
        )

    def insert_batch(self, entries: list[dict]) -> None:
        for e in entries:
            row = self.db.fetchone("SELECT nextval('time_entries_id_seq')")
            eid = int(row[0])
            self.db.execute(
                """
                INSERT INTO time_entries
                    (id, user_id, entry_date, time_from, time_to, description, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    eid,
                    e["user_id"],
                    e["entry_date"],
                    e.get("time_from"),
                    e.get("time_to"),
                    e.get("description") or "",
                    e.get("sort_order", 0),
                ],
            )


# ---------------------------------------------------------------------------
# Month closures
# ---------------------------------------------------------------------------


class MonthClosureRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def is_closed(self, user_id: int, year: int, month: int) -> bool:
        row = self.db.fetchone(
            """
            SELECT is_closed FROM month_closures
            WHERE user_id = ? AND year = ? AND month = ?
            """,
            [user_id, year, month],
        )
        return bool(row[0]) if row else False

    def set_closed(self, user_id: int, year: int, month: int, closed: bool) -> None:
        existing = self.db.fetchone(
            """
            SELECT 1 FROM month_closures
            WHERE user_id = ? AND year = ? AND month = ?
            """,
            [user_id, year, month],
        )
        if existing:
            self.db.execute(
                """
                UPDATE month_closures SET is_closed = ?
                WHERE user_id = ? AND year = ? AND month = ?
                """,
                [closed, user_id, year, month],
            )
        else:
            self.db.execute(
                """
                INSERT INTO month_closures (user_id, year, month, is_closed)
                VALUES (?, ?, ?, ?)
                """,
                [user_id, year, month, closed],
            )


# ---------------------------------------------------------------------------
# Absences
# ---------------------------------------------------------------------------


class AbsenceRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_for_month(self, user_id: int, year: int, month: int) -> list[Absence]:
        # Absences that overlap the month
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1)
        else:
            month_end = date(year, month + 1, 1)
        rows = self.db.fetchall(
            """
            SELECT id, user_id, date_from, date_to, hours, description
            FROM absences
            WHERE user_id = ?
              AND date_from < ?
              AND date_to >= ?
            ORDER BY date_from, id
            """,
            [user_id, month_end, month_start],
        )
        return [self._from_row(r) for r in rows]

    def list_all_for_user(self, user_id: int) -> list[Absence]:
        rows = self.db.fetchall(
            """
            SELECT id, user_id, date_from, date_to, hours, description
            FROM absences WHERE user_id = ? ORDER BY date_from DESC, id
            """,
            [user_id],
        )
        return [self._from_row(r) for r in rows]

    def delete_for_month(self, user_id: int, year: int, month: int) -> None:
        """Delete absences whose date_from falls in the given month."""
        self.db.execute(
            """
            DELETE FROM absences
            WHERE user_id = ? AND year(date_from) = ? AND month(date_from) = ?
            """,
            [user_id, year, month],
        )

    def insert_batch(self, items: list[dict]) -> None:
        for a in items:
            row = self.db.fetchone("SELECT nextval('absences_id_seq')")
            aid = int(row[0])
            self.db.execute(
                """
                INSERT INTO absences
                    (id, user_id, date_from, date_to, hours, description)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    aid,
                    a["user_id"],
                    a["date_from"],
                    a["date_to"],
                    a.get("hours"),
                    a.get("description") or "",
                ],
            )

    def has_overlap_with_dates(
        self, user_id: int, date_from: date, date_to: date, exclude_ids: set[int] | None = None
    ) -> bool:
        rows = self.db.fetchall(
            """
            SELECT id FROM absences
            WHERE user_id = ? AND date_from <= ? AND date_to >= ?
            """,
            [user_id, date_to, date_from],
        )
        exclude = exclude_ids or set()
        return any(r[0] not in exclude for r in rows)

    @staticmethod
    def _from_row(r: tuple) -> Absence:
        return Absence(
            id=r[0],
            user_id=r[1],
            date_from=r[2] if isinstance(r[2], date) else date.fromisoformat(str(r[2])),
            date_to=r[3] if isinstance(r[3], date) else date.fromisoformat(str(r[3])),
            hours=float(r[4]) if r[4] is not None else None,
            description=r[5] or "",
        )
