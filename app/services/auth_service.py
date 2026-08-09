"""Authentication and session management."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from app.config import AppConfig
from app.db.repositories import SessionRepository, SessionRow, User, UserRepository
from app.logger import log
from app.security import (
    generate_csrf_token,
    generate_token,
    hash_password,
    validate_password,
    validate_username,
    verify_password,
)
from app.services.time_utils import now_local


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        sessions: SessionRepository,
        config: AppConfig,
    ) -> None:
        self.users = users
        self.sessions = sessions
        self.config = config

    def registration_allowed(self) -> bool:
        # First user may always register (becomes admin)
        if self.users.count() == 0:
            return True
        return bool(self.config.allow_user_registration)

    def register(
        self,
        username: str,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        password_repeat: str,
    ) -> tuple[Optional[User], Optional[str]]:
        if not self.registration_allowed():
            return None, "Registrierung ist deaktiviert"

        username = (username or "").strip()
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        email = (email or "").strip()

        err = validate_username(username)
        if err:
            return None, err
        if not first_name or not last_name:
            return None, "Vorname und Nachname sind erforderlich"
        if not email:
            return None, "E-Mail ist erforderlich"
        if password != password_repeat:
            return None, "Passwörter stimmen nicht überein"
        pw_err = validate_password(password)
        if pw_err:
            return None, pw_err
        if self.users.username_exists(username):
            return None, "Benutzername ist bereits vergeben"

        is_first = self.users.count() == 0
        user = self.users.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=hash_password(password),
            is_admin=is_first,
        )
        if is_first:
            log.info("First user created as administrator: %s", username)
        else:
            log.info("User registered: %s", username)
        return user, None

    def login(self, username: str, password: str) -> tuple[Optional[str], Optional[str], Optional[User]]:
        """
        Returns (session_id, error_message, user).
        Generic error for invalid credentials (OWASP).
        """
        username = (username or "").strip()
        user = self.users.get_by_username(username)
        if not user or not verify_password(password, user.password_hash):
            log.warning("Failed login attempt for username=%s", username)
            return None, "Ungültige Login Daten", None
        if user.is_locked:
            log.warning("Locked user login attempt: %s", username)
            return None, "Ihr Benutzerkonto ist gesperrt. Bitte kontaktieren Sie einen Administrator.", None

        session_id = generate_token(32)
        csrf = generate_csrf_token()
        hard = now_local() + timedelta(minutes=self.config.session_timeout_hard_min)
        self.sessions.create(session_id, user.id, hard, csrf)
        log.info("User logged in: %s", username)
        return session_id, None, user

    def logout(self, session_id: Optional[str]) -> None:
        if session_id:
            self.sessions.delete(session_id)
            log.info("Session invalidated")

    def resolve_session(
        self, session_id: Optional[str]
    ) -> tuple[Optional[User], Optional[SessionRow]]:
        if not session_id:
            return None, None
        sess = self.sessions.get(session_id)
        if not sess:
            return None, None

        now = now_local()
        idle_limit = timedelta(minutes=self.config.session_timeout_idle_min)

        # Normalize datetimes (DuckDB may return naive datetimes)
        last = sess.last_activity
        hard = sess.expires_hard
        if isinstance(last, str):
            last = datetime.fromisoformat(last)
        if isinstance(hard, str):
            hard = datetime.fromisoformat(hard)

        if hard < now:
            self.sessions.delete(session_id)
            log.info("Session expired (hard timeout)")
            return None, None
        if last < now - idle_limit:
            self.sessions.delete(session_id)
            log.info("Session expired (idle timeout)")
            return None, None

        user = self.users.get_by_id(sess.user_id)
        if not user or user.is_locked:
            self.sessions.delete(session_id)
            return None, None

        self.sessions.touch(session_id)
        return user, sess

    def change_password(
        self, user: User, current: str, new_pw: str, new_repeat: str
    ) -> Optional[str]:
        if not verify_password(current, user.password_hash):
            return "Aktuelles Passwort ist falsch"
        if new_pw != new_repeat:
            return "Passwörter stimmen nicht überein"
        err = validate_password(new_pw)
        if err:
            return err
        self.users.update_password(user.id, hash_password(new_pw))
        log.info("Password changed for user id=%s", user.id)
        return None

    def admin_reset_password(self, user_id: int, new_pw: str) -> Optional[str]:
        err = validate_password(new_pw)
        if err:
            return err
        self.users.update_password(user_id, hash_password(new_pw))
        self.sessions.delete_for_user(user_id)
        log.info("Admin reset password for user id=%s", user_id)
        return None
