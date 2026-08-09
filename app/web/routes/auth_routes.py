"""Login, logout, registration."""

from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from app.web.helpers import (
    clear_session_cookie,
    get_auth,
    load_current_user,
    set_session_cookie,
)

bp = Blueprint("auth", __name__)


@bp.route("/")
def index():
    user, _ = load_current_user()
    if user:
        return redirect(url_for("time.time_entry"))
    return redirect(url_for("auth.login"))


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

    return render_template(
        "login.html",
        error=error,
        registration_allowed=auth.registration_allowed(),
    )


@bp.route("/logout", methods=["POST", "GET"])
def logout():
    from app.web.helpers import SESSION_COOKIE

    sid = request.cookies.get(SESSION_COOKIE)
    get_auth().logout(sid)
    resp = make_response(redirect(url_for("auth.login")))
    return clear_session_cookie(resp)


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
