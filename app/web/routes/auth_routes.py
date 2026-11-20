"""Login, logout, registration."""

from __future__ import annotations

import json
import time

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from app.logger import log
from app.web.rate_limit import AttemptLimiter
from app.web.helpers import (
    SESSION_COOKIE,
    clear_session_cookie,
    get_auth,
    load_current_user,
    require_csrf,
    set_session_cookie,
)

bp = Blueprint("auth", __name__)


_TOO_MANY_ATTEMPTS = "Zu viele Anmeldeversuche. Bitte später erneut versuchen."


def _client_ip() -> str:
    return request.remote_addr or "unknown"


def _attempt_key(kind: str, name: str) -> str:
    return f"{kind}:{(name or '').strip().lower()}"


def _limiter() -> AttemptLimiter:
    return current_app.config["LOGIN_LIMIT"]


def _register_error_field(error: str | None) -> str | None:
    if not error:
        return None
    if error.startswith("Benutzername"):
        return "username"
    if "Vorname" in error or "Nachname" in error:
        return "name"
    if "E-Mail" in error:
        return "email"
    if "Passwort" in error:
        return "password"
    return None


@bp.route("/")
def index():
    user, _ = load_current_user()
    if user:
        return redirect(url_for("time.time_entry"))
    return redirect(url_for("auth.login"))


@bp.route("/favicon.ico")
def favicon():
    """Browsers often request /favicon.ico at the site root."""
    static = current_app.static_folder
    return send_from_directory(static, "favicon.ico", mimetype="image/x-icon")


@bp.route("/login", methods=["GET", "POST"])
def login():
    user, _ = load_current_user()
    if user:
        return redirect(url_for("time.time_entry"))

    auth = get_auth()
    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        limit_name = _attempt_key("login", username)
        ip = _client_ip()
        if _limiter().is_blocked(ip, limit_name):
            log.warning("Login rate limit reached for username=%s", username.strip())
            error = _TOO_MANY_ATTEMPTS
            return (
                render_template(
                    "login.html",
                    error=error,
                    username=username,
                    registration_allowed=auth.registration_allowed(),
                ),
                429,
            )
        session_id, error, _user = auth.login(username, password)
        if session_id:
            _limiter().record_success(limit_name)
            resp = make_response(redirect(url_for("time.time_entry")))
            return set_session_cookie(resp, session_id)
        _limiter().record_failure(ip, limit_name)
    elif request.args.get("timeout") == "1":
        error = "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an."

    return render_template(
        "login.html",
        error=error,
        username=username,
        registration_allowed=auth.registration_allowed(),
    )


@bp.route("/logout", methods=["POST"])
def logout():
    sid = request.cookies.get(SESSION_COOKIE)
    _user, sess = load_current_user()
    if sess is not None:
        err = require_csrf()
        if err:
            abort(400)
    get_auth().logout(sid)
    if request.form.get("reason") == "timeout":
        resp = make_response(redirect(url_for("auth.login", timeout=1)))
    else:
        resp = make_response(redirect(url_for("auth.login")))
    return clear_session_cookie(resp)


@bp.route("/session/status")
def session_status():
    """JSON status for fallback polling – does not reset idle timeout."""
    sid = request.cookies.get(SESSION_COOKIE)
    status = get_auth().peek_session_status(sid)
    code = 200 if status.get("active") else 401
    return jsonify(status), code


@bp.route("/session/events")
def session_events():
    """
    Server-Sent Events stream that notifies the browser when the session expires.
    Peek-only checks so the idle timer is not extended by the watchdog itself.
    """
    sid = request.cookies.get(SESSION_COOKIE)
    auth = get_auth()

    def generate():
        # Initial status immediately
        while True:
            try:
                status = auth.peek_session_status(sid)
            except Exception:
                log.exception("Session watchdog check failed")
                yield f"event: session-expired\ndata: {json.dumps({'reason': 'error'})}\n\n"
                break

            if not status.get("active"):
                payload = json.dumps({"reason": status.get("reason") or "expired"})
                yield f"event: session-expired\ndata: {payload}\n\n"
                break

            remaining = max(0, int(status.get("seconds_remaining") or 0))
            payload = json.dumps(
                {
                    "seconds_remaining": remaining,
                    "seconds_idle": int(status.get("seconds_idle") or 0),
                    "seconds_hard": int(status.get("seconds_hard") or 0),
                }
            )
            yield f"event: session-ok\ndata: {payload}\n\n"

            # Sleep until near expiry; cap so keepalives continue and DB is re-checked
            wait = remaining if remaining > 0 else 1
            wait = min(wait, 10)
            time.sleep(wait)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(generate(), mimetype="text/event-stream", headers=headers)


@bp.route("/register", methods=["GET", "POST"])
def register():
    auth = get_auth()
    if not auth.registration_allowed():
        return redirect(url_for("auth.login"))

    user, _ = load_current_user()
    if user:
        return redirect(url_for("time.time_entry"))

    error = None
    error_field = None
    form = {"username": "", "first_name": "", "last_name": "", "email": ""}
    if request.method == "POST":
        form = {
            "username": request.form.get("username", ""),
            "first_name": request.form.get("first_name", ""),
            "last_name": request.form.get("last_name", ""),
            "email": request.form.get("email", ""),
        }
        limit_name = _attempt_key("register", form["username"])
        ip = _client_ip()
        if _limiter().is_blocked(ip, limit_name):
            log.warning("Registration rate limit reached for username=%s", form["username"].strip())
            error = _TOO_MANY_ATTEMPTS
            return render_template("register.html", error=error, error_field=None, form=form), 429
        new_user, error = auth.register(
            username=form["username"],
            first_name=form["first_name"],
            last_name=form["last_name"],
            email=form["email"],
            password=request.form.get("password", ""),
            password_repeat=request.form.get("password_repeat", ""),
        )
        if new_user and not error:
            # Auto-login after registration
            session_id, login_err, _ = auth.login(
                form["username"],
                request.form.get("password", ""),
            )
            if session_id:
                _limiter().record_success(limit_name)
                resp = make_response(redirect(url_for("time.time_entry")))
                return set_session_cookie(resp, session_id)
            error = login_err or "Registrierung erfolgreich, Anmeldung fehlgeschlagen."
        else:
            _limiter().record_failure(ip, limit_name)
        error_field = _register_error_field(error)

    return render_template("register.html", error=error, error_field=error_field, form=form)
