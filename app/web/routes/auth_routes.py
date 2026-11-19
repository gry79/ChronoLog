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
from app.web.helpers import (
    SESSION_COOKIE,
    clear_session_cookie,
    get_auth,
    load_current_user,
    require_csrf,
    set_session_cookie,
)

bp = Blueprint("auth", __name__)


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
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        session_id, error, _user = auth.login(username, password)
        if session_id:
            resp = make_response(redirect(url_for("time.time_entry")))
            return set_session_cookie(resp, session_id)
    elif request.args.get("timeout") == "1":
        error = "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an."

    return render_template(
        "login.html",
        error=error,
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
    if request.method == "POST":
        new_user, error = auth.register(
            username=request.form.get("username", ""),
            first_name=request.form.get("first_name", ""),
            last_name=request.form.get("last_name", ""),
            email=request.form.get("email", ""),
            password=request.form.get("password", ""),
            password_repeat=request.form.get("password_repeat", ""),
        )
        if new_user and not error:
            # Auto-login after registration
            session_id, login_err, _ = auth.login(
                request.form.get("username", ""),
                request.form.get("password", ""),
            )
            if session_id:
                resp = make_response(redirect(url_for("time.time_entry")))
                return set_session_cookie(resp, session_id)
            error = login_err or "Registration succeeded but login failed"

    return render_template("register.html", error=error)
