"""Schema migrations – applied on startup, never destructive to user data."""

from __future__ import annotations

from app.db.connection import Database
from app.logger import log

# Each migration is (version, description, list of SQL statements).
# Migrations must be additive/safe. Data-changing migrations copy data carefully.
MIGRATIONS: list[tuple[int, str, list[str]]] = [
    (
        1,
        "Initial schema",
        [
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                description VARCHAR NOT NULL,
                applied_at TIMESTAMP NOT NULL DEFAULT current_timestamp
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username VARCHAR NOT NULL UNIQUE,
                first_name VARCHAR NOT NULL,
                last_name VARCHAR NOT NULL,
                email VARCHAR NOT NULL,
                password_hash VARCHAR NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                is_locked BOOLEAN NOT NULL DEFAULT FALSE,
                chronos_id INTEGER,
                start_year INTEGER,
                start_month INTEGER,
                initial_balance DOUBLE NOT NULL DEFAULT 0.0,
                created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
                updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
            )
            """,
            """
            CREATE SEQUENCE IF NOT EXISTS users_id_seq START 1
            """,
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id VARCHAR PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
                last_activity TIMESTAMP NOT NULL DEFAULT current_timestamp,
                expires_hard TIMESTAMP NOT NULL,
                csrf_token VARCHAR NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chronos (
                id INTEGER PRIMARY KEY,
                name VARCHAR NOT NULL,
                daily_target_hours DOUBLE NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
                updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
            )
            """,
            """
            CREATE SEQUENCE IF NOT EXISTS chronos_id_seq START 1
            """,
            """
            CREATE TABLE IF NOT EXISTS chronos_special_days (
                id INTEGER PRIMARY KEY,
                chronos_id INTEGER NOT NULL,
                month INTEGER NOT NULL,
                day INTEGER NOT NULL,
                year INTEGER,
                target_hours DOUBLE NOT NULL,
                description VARCHAR NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE SEQUENCE IF NOT EXISTS chronos_special_days_id_seq START 1
            """,
            """
            CREATE TABLE IF NOT EXISTS time_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                entry_date DATE NOT NULL,
                time_from VARCHAR,
                time_to VARCHAR,
                description VARCHAR NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
                updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
            )
            """,
            """
            CREATE SEQUENCE IF NOT EXISTS time_entries_id_seq START 1
            """,
            """
            CREATE TABLE IF NOT EXISTS month_closures (
                user_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                is_closed BOOLEAN NOT NULL DEFAULT FALSE,
                PRIMARY KEY (user_id, year, month)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS absences (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                date_from DATE NOT NULL,
                date_to DATE NOT NULL,
                hours DOUBLE,
                description VARCHAR NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
                updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
            )
            """,
            """
            CREATE SEQUENCE IF NOT EXISTS absences_id_seq START 1
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_time_entries_user_date
                ON time_entries(user_id, entry_date)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_absences_user
                ON absences(user_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_user
                ON sessions(user_id)
            """,
        ],
    ),
]


def _current_version(db: Database) -> int:
    try:
        row = db.fetchone(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        )
        return int(row[0]) if row else 0
    except Exception:
        # Table does not exist yet
        return 0


def run_migrations(db: Database) -> None:
    """Apply all pending migrations in order without data loss."""
    current = _current_version(db)
    pending = [m for m in MIGRATIONS if m[0] > current]

    if not pending:
        log.info("Database schema is up to date (version %s)", current)
        return

    for version, description, statements in pending:
        log.info("Applying migration v%s: %s", version, description)
        for sql in statements:
            db.execute(sql)
        # Ensure migrations table exists before insert (v1 creates it first)
        db.execute(
            """
            INSERT INTO schema_migrations (version, description)
            VALUES (?, ?)
            """,
            [version, description],
        )
        log.info("Migration v%s applied successfully", version)

    log.info("All migrations complete (now at version %s)", pending[-1][0])
