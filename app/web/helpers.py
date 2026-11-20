"""Shared request helpers for routes."""

from __future__ import annotations

from functools import wraps
from typing import Callable, Optional

from flask import (
    current_app,
    g,
    redirect,
    request,
    url_for,
    abort,
)

from app.db.repositories import SessionRow, User
from app.logger import log
from app.security import constant_time_equals


SESSION_COOKIE = "chronolog_session"


def get_auth():
    return current_app.config["AUTH"]


def get_config():
    return current_app.config["APP_CONFIG"]


def load_current_user() -> tuple[Optional[User], Optional[SessionRow]]:
    sid = request.cookies.get(SESSION_COOKIE)
    user, sess = get_auth().resolve_session(sid)
    g.current_user = user
    g.session_row = sess
    g.csrf_token = sess.csrf_token if sess else None
    return user, sess


def login_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user, _ = load_current_user()
        if not user:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user, _ = load_current_user()
        if not user:
            return redirect(url_for("auth.login"))
        if not user.is_admin:
            log.warning("Denied admin access for user id=%s path=%s", user.id, request.path)
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def require_csrf() -> Optional[str]:
    """Validate CSRF token from form or header. Returns error message or None."""
    sess: Optional[SessionRow] = getattr(g, "session_row", None)
    if not sess:
        return "Nicht angemeldet"
    token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not token or not constant_time_equals(token, sess.csrf_token):
        return "Ungültiges CSRF-Token"
    return None


def set_session_cookie(response, session_id: str):
    cfg = get_config()
    max_age = cfg.session_timeout_hard_min * 60
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=max_age,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure,
        path="/",
    )
    return response


def clear_session_cookie(response):
    response.set_cookie(
        SESSION_COOKIE,
        "",
        max_age=0,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure,
        path="/",
    )
    return response
