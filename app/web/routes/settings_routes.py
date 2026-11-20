"""User settings routes."""

from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from app.security import validate_username
from app.services.time_utils import parse_decimal
from app.web.helpers import clear_session_cookie, login_required, require_csrf

bp = Blueprint("settings", __name__)


def _profile_from_user(user) -> dict:
    return {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "chronos_id": "" if user.chronos_id is None else str(user.chronos_id),
        "start_year": "" if not user.start_year else str(user.start_year),
        "start_month": "" if not user.start_month else str(user.start_month),
        "initial_balance": f"{user.initial_balance:.1f}",
    }


def _posted_profile() -> dict:
    return {
        "username": request.form.get("username") or "",
        "first_name": request.form.get("first_name") or "",
        "last_name": request.form.get("last_name") or "",
        "chronos_id": request.form.get("chronos_id") or "",
        "start_year": request.form.get("start_year") or "",
        "start_month": request.form.get("start_month") or "",
        "initial_balance": request.form.get("initial_balance") or "",
    }


def _render_settings(user, profile, field_errors=None, password_error=""):
    return render_template(
        "settings.html",
        user=user,
        profile=profile,
        field_errors=field_errors or {},
        password_error=password_error,
        all_chronos=current_app.config["CHRONOS_REPO"].list_all(),
        csrf_token=g.csrf_token,
        active_nav="settings",
    )


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    users = current_app.config["USERS"]
    chronos_repo = current_app.config["CHRONOS_REPO"]
    auth = current_app.config["AUTH"]
    user = users.get_by_id(g.current_user.id)

    if request.method == "POST":
        action = request.form.get("action", "profile")
        if action == "password":
            err = require_csrf()
            if err:
                flash(err, "error")
                return _render_settings(user, _profile_from_user(user), password_error=err)
            msg = auth.change_password(
                user,
                request.form.get("current_password", ""),
                request.form.get("new_password", ""),
                request.form.get("new_password_repeat", ""),
            )
            if msg:
                flash(msg, "error")
                return _render_settings(user, _profile_from_user(user), password_error=msg)
            flash("Passwort geändert. Bitte melden Sie sich erneut an.", "success")
            resp = make_response(redirect(url_for("auth.login")))
            return clear_session_cookie(resp)

        posted = _posted_profile()

        def fail(message: str, **errors):
            flash(message, "error")
            return _render_settings(user, posted, field_errors=errors)

        err = require_csrf()
        if err:
            return fail(err)

        username = posted["username"].strip()
        first_name = posted["first_name"].strip()
        last_name = posted["last_name"].strip()
        uerr = validate_username(username)
        if uerr:
            return fail(uerr, username=uerr)
        if users.username_exists(username, exclude_id=user.id):
            message = "Benutzername bereits vergeben."
            return fail(message, username=message)
        if not first_name or not last_name:
            message = "Vorname und Nachname sind erforderlich."
            errors = {}
            if not first_name:
                errors["first_name"] = "Vorname ist erforderlich."
            if not last_name:
                errors["last_name"] = "Nachname ist erforderlich."
            return fail(message, **errors)

        field_errors: dict[str, str] = {}
        start_year = None
        start_month = None
        chronos_id = None
        year_raw = posted["start_year"].strip()
        month_raw = posted["start_month"].strip()
        if year_raw:
            try:
                start_year = int(year_raw)
            except ValueError:
                field_errors["start_year"] = "Startjahr ist ungültig."
            else:
                if not (1970 <= start_year <= 2100):
                    field_errors["start_year"] = "Startjahr muss zwischen 1970 und 2100 liegen."
        if month_raw:
            try:
                start_month = int(month_raw)
            except ValueError:
                field_errors["start_month"] = "Startmonat ist ungültig."
            else:
                if not (1 <= start_month <= 12):
                    field_errors["start_month"] = "Startmonat muss zwischen 1 und 12 liegen."
        try:
            initial_balance = parse_decimal(posted["initial_balance"].strip() or "0")
        except ValueError:
            field_errors["initial_balance"] = "Ungültiges Zeitkonto."
            initial_balance = 0.0
        chronos_raw = posted["chronos_id"].strip()
        if chronos_raw:
            try:
                chronos_id = int(chronos_raw)
            except ValueError:
                field_errors["chronos_id"] = "Chronos nicht gefunden."
            else:
                if chronos_repo.get(chronos_id) is None:
                    field_errors["chronos_id"] = "Chronos nicht gefunden."
        if field_errors:
            message = next(iter(field_errors.values()))
            flash(message, "error")
            return _render_settings(user, posted, field_errors=field_errors)

        users.update_profile(
            user.id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            chronos_id=chronos_id,
            start_year=start_year,
            start_month=start_month,
            initial_balance=initial_balance,
        )
        flash("Einstellungen gespeichert.", "success")
        return redirect(url_for("settings.settings"))

    return _render_settings(user, _profile_from_user(user))
