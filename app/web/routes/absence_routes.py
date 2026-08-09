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


@bp.route("/absences")
@login_required
def absences():
    user = g.current_user
    year, month = _parse_ym()
    time_svc = current_app.config["TIME_SVC"]
    year, month = time_svc.clamp_month(user, year, month)

    absence_svc = current_app.config["ABSENCE_SVC"]
    items = absence_svc.list_for_month(user, year, month)
    is_closed = current_app.config["TIME_SVC"].month_repo.is_closed(user.id, year, month)

    sy, sm = current_app.config["BALANCE_SVC"].start_year_month(user)
    can_prev = (year, month) > (sy, sm)
    today = date.today()
    can_next = (year, month) < (today.year, today.month)

    return render_template(
        "absences.html",
        user=user,
        year=year,
        month=month,
        label=month_label_de(year, month),
        items=items,
        is_closed=is_closed,
        can_prev=can_prev,
        can_next=can_next,
        csrf_token=g.csrf_token,
        active_nav="absences",
    )


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
    err = require_csrf()
    if err:
        flash(err, "error")
        return redirect(url_for("absence.absences"))

    user = g.current_user
    year = int(request.form.get("year"))
    month = int(request.form.get("month"))

    if current_app.config["TIME_SVC"].month_repo.is_closed(user.id, year, month):
        flash("Monat ist abgeschlossen und kann nicht bearbeitet werden.", "error")
        return redirect(url_for("absence.absences", year=year, month=month))

    dates_from = request.form.getlist("date_from")
    dates_to = request.form.getlist("date_to")
    hours = request.form.getlist("hours")
    descs = request.form.getlist("description")

    rows = []
    for i in range(len(dates_from)):
        rows.append(
            {
                "date_from": dates_from[i],
                "date_to": dates_to[i] if i < len(dates_to) else dates_from[i],
                "hours": hours[i] if i < len(hours) else "",
                "description": descs[i] if i < len(descs) else "",
            }
        )

    error = current_app.config["ABSENCE_SVC"].save_for_month(user, year, month, rows)
    if error:
        flash(error, "error")
    else:
        flash("Absenzen gespeichert.", "success")
    return redirect(url_for("absence.absences", year=year, month=month))
