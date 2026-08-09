"""User settings routes."""

from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from app.security import validate_username
from app.web.helpers import login_required, require_csrf

bp = Blueprint("settings", __name__)


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = g.current_user
    users = current_app.config["USERS"]
    chronos_repo = current_app.config["CHRONOS_REPO"]
    auth = current_app.config["AUTH"]
    all_chronos = chronos_repo.list_all()

    if request.method == "POST":
        err = require_csrf()
        if err:
            flash(err, "error")
            return redirect(url_for("settings.settings"))

        action = request.form.get("action", "profile")

        if action == "password":
            msg = auth.change_password(
                user,
                request.form.get("current_password", ""),
                request.form.get("new_password", ""),
                request.form.get("new_password_repeat", ""),
            )
            if msg:
                flash(msg, "error")
            else:
                flash("Passwort geändert.", "success")
            return redirect(url_for("settings.settings"))

        username = (request.form.get("username") or "").strip()
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        uerr = validate_username(username)
        if uerr:
            flash(uerr, "error")
            return redirect(url_for("settings.settings"))
        if users.username_exists(username, exclude_id=user.id):
            flash("Benutzername bereits vergeben.", "error")
            return redirect(url_for("settings.settings"))
        if not first_name or not last_name:
            flash("Vorname und Nachname sind erforderlich.", "error")
            return redirect(url_for("settings.settings"))

        try:
            start_year = int(request.form.get("start_year") or 0) or None
            start_month = int(request.form.get("start_month") or 0) or None
            initial_balance = float(
                (request.form.get("initial_balance") or "0").replace(",", ".")
            )
            chronos_raw = request.form.get("chronos_id") or ""
            chronos_id = int(chronos_raw) if chronos_raw else None
        except ValueError:
            flash("Ungültige Eingabewerte.", "error")
            return redirect(url_for("settings.settings"))

        if start_month is not None and not (1 <= start_month <= 12):
            flash("Startmonat muss zwischen 1 und 12 liegen.", "error")
            return redirect(url_for("settings.settings"))

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

    # Refresh user
    user = users.get_by_id(user.id)
    return render_template(
        "settings.html",
        user=user,
        all_chronos=all_chronos,
        csrf_token=g.csrf_token,
        active_nav="settings",
    )
