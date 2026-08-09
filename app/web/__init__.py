"""Flask web application factory."""

from __future__ import annotations

from pathlib import Path

from flask import Flask

from app.config import AppConfig
from app.db.connection import Database
from app.db.migrations import run_migrations
from app.db.repositories import (
    AbsenceRepository,
    ChronosRepository,
    MonthClosureRepository,
    SessionRepository,
    TimeEntryRepository,
    UserRepository,
)
from app.logger import log
from app.services.absence_service import AbsenceService
from app.services.auth_service import AuthService
from app.services.balance_service import BalanceService
from app.services.chronos_service import ChronosService
from app.services.time_service import TimeService


def create_app(config: AppConfig, db: Database) -> Flask:
    root = Path(__file__).resolve().parents[2]
    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
    )
    # Secret key for Flask flash messages / signing – sessions are server-side
    app.config["SECRET_KEY"] = _ensure_secret(root / "data" / ".secret_key")
    app.config["APP_CONFIG"] = config
    app.config["DB"] = db

    # Repositories
    users = UserRepository(db)
    sessions = SessionRepository(db)
    chronos_repo = ChronosRepository(db)
    time_repo = TimeEntryRepository(db)
    absence_repo = AbsenceRepository(db)
    month_repo = MonthClosureRepository(db)

    # Services
    chronos_service = ChronosService(chronos_repo)
    balance_service = BalanceService(time_repo, absence_repo, month_repo, chronos_service)
    auth_service = AuthService(users, sessions, config)
    time_service = TimeService(time_repo, month_repo, chronos_service, balance_service)
    absence_service = AbsenceService(absence_repo, time_repo, chronos_service)

    app.config["USERS"] = users
    app.config["SESSIONS"] = sessions
    app.config["CHRONOS_REPO"] = chronos_repo
    app.config["AUTH"] = auth_service
    app.config["TIME_SVC"] = time_service
    app.config["ABSENCE_SVC"] = absence_service
    app.config["CHRONOS_SVC"] = chronos_service
    app.config["BALANCE_SVC"] = balance_service

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # CSP allows HTMX/Tailwind CDNs and inline styles for Tailwind play CDN
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net https://cdn.tailwindcss.com 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        return response

    from app.web.routes.auth_routes import bp as auth_bp
    from app.web.routes.time_routes import bp as time_bp
    from app.web.routes.absence_routes import bp as absence_bp
    from app.web.routes.settings_routes import bp as settings_bp
    from app.web.routes.admin_routes import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(time_bp)
    app.register_blueprint(absence_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(admin_bp)

    log.info("Flask application created")
    return app


def _ensure_secret(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    import secrets

    key = secrets.token_hex(32)
    path.write_text(key, encoding="utf-8")
    path.chmod(0o600)
    return key


def init_database(db: Database) -> None:
    run_migrations(db)
