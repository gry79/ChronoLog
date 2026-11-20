"""Absence entry routes."""

from __future__ import annotations

from datetime import date

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

from app.services.time_utils import month_label_de, next_month, prev_month
from app.web.helpers import login_required, require_csrf

bp = Blueprint("absence", __name__)


def _parse_ym():
    today = date.today()
    try:
        year = int(request.args.get("year", request.form.get("year", today.year)))
        month = int(request.args.get("month", request.form.get("month", today.month)))
    except ValueError:
        year, month = today.year, today.month
    return year, month


def _render_absences(user, year: int, month: int, items):
    time_svc = current_app.config["TIME_SVC"]
    year, month = time_svc.clamp_month(user, year, month)
    is_closed = time_svc.month_repo.is_closed(user.id, year, month)
    sy, sm = current_app.config["BALANCE_SVC"].start_year_month(user)
    today = date.today()
    return render_template(
        "absences.html",
        user=user,
        year=year,
        month=month,
        label=month_label_de(year, month),
        items=items,
        is_closed=is_closed,
        can_prev=(year, month) > (sy, sm),
        can_next=(year, month) < (today.year, today.month),
        csrf_token=g.csrf_token,
        active_nav="absences",
    )


def _posted_absence_rows() -> list[dict]:
    dates_from = request.form.getlist("date_from")
    dates_to = request.form.getlist("date_to")
    hours = request.form.getlist("hours")
    descs = request.form.getlist("description")
    count = max(len(dates_from), len(dates_to), len(hours), len(descs), 0)
    rows = []
    for i in range(count):
        rows.append(
            {
                "date_from": dates_from[i] if i < len(dates_from) else "",
                "date_to": dates_to[i] if i < len(dates_to) else "",
                "hours": hours[i] if i < len(hours) else "",
                "description": descs[i] if i < len(descs) else "",
                "error": "",
            }
        )
    return rows


@bp.route("/absences")
@login_required
def absences():
    user = g.current_user
    year, month = _parse_ym()
    year, month = current_app.config["TIME_SVC"].clamp_month(user, year, month)
    items = current_app.config["ABSENCE_SVC"].list_for_month(user, year, month)
    return _render_absences(user, year, month, items)


@bp.route("/absences/nav")
@login_required
def absences_nav():
    user = g.current_user
    year, month = _parse_ym()
    direction = request.args.get("dir", "")
    time_svc = current_app.config["TIME_SVC"]
    year, month = time_svc.clamp_month(user, year, month)
    if direction == "prev":
        year, month = prev_month(year, month)
        year, month = time_svc.clamp_month(user, year, month)
    elif direction == "next":
        today = date.today()
        ny, nm = next_month(year, month)
        if (ny, nm) <= (today.year, today.month):
            year, month = ny, nm
    return redirect(url_for("absence.absences", year=year, month=month))


@bp.route("/absences/save", methods=["POST"])
@login_required
def absences_save():
    user = g.current_user
    rows = _posted_absence_rows()
    try:
        year = int(request.form.get("year", ""))
        month = int(request.form.get("month", ""))
    except (TypeError, ValueError):
        flash("Ungültiger Monat.", "error")
        today = date.today()
        return _render_absences(user, today.year, today.month, rows)

    def fail(message: str):
        flash(message, "error")
        return _render_absences(user, year, month, rows)

    err = require_csrf()
    if err:
        return fail(err)

    if current_app.config["TIME_SVC"].month_repo.is_closed(user.id, year, month):
        return fail("Monat ist abgeschlossen und kann nicht bearbeitet werden.")

    error = current_app.config["ABSENCE_SVC"].save_for_month(user, year, month, rows)
    if error:
        return fail(error)
    flash("Absenzen gespeichert.", "success")
    return redirect(url_for("absence.absences", year=year, month=month))
