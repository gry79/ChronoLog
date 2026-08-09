"""Security helpers: password hashing, tokens, CSRF, validation."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from typing import Optional

import bcrypt

from app.logger import log

_PASSWORD_MIN_LEN = 6
_PASSWORD_HAS_LETTER = re.compile(r"[A-Za-z]")
_PASSWORD_HAS_DIGIT = re.compile(r"\d")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{2,64}$")


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        log.warning("Password verification failed due to invalid hash format")
        return False


def validate_password(password: str) -> Optional[str]:
    """Return an error message if the password is invalid, else None."""
    if len(password) < _PASSWORD_MIN_LEN:
        return f"Das Passwort muss mindestens {_PASSWORD_MIN_LEN} Zeichen lang sein"
    if not _PASSWORD_HAS_LETTER.search(password):
        return "Das Passwort muss mindestens einen Buchstaben enthalten"
    if not _PASSWORD_HAS_DIGIT.search(password):
        return "Das Passwort muss mindestens eine Zahl enthalten"
    return None


def validate_username(username: str) -> Optional[str]:
    """Return an error message if the username is invalid, else None."""
    if not username or not _USERNAME_RE.match(username):
        return "Benutzername: 2–64 Zeichen (Buchstaben, Ziffern, . _ @ -)"
    return None


def generate_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(nbytes)


def generate_csrf_token() -> str:
    return generate_token(24)


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def hash_token(token: str) -> str:
    """One-way hash of a session token for storage (defense in depth)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
