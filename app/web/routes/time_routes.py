"""Time entry UI routes."""

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

from app.services.time_utils import next_month, prev_month
from app.web.helpers import login_required, require_csrf

bp = Blueprint("time", __name__)


def _parse_ym():
    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
    except ValueError:
        year, month = today.year, today.month
    if not (1 <= month <= 12):
        month = today.month
    return year, month


@bp.route("/time")
@login_required
def time_entry():
    user = g.current_user
    year, month = _parse_ym()
    time_svc = current_app.config["TIME_SVC"]

    expand_raw = request.args.getlist("expand")
    expand_dates = set()
    for s in expand_raw:
        try:
            expand_dates.add(date.fromisoformat(s))
        except ValueError:
            pass

    view = time_svc.build_month_view(user, year, month, expand_dates)
    return render_template(
        "time_entry.html",
        view=view,
        user=user,
        csrf_token=g.csrf_token,
        active_nav="time",
        expand_list=sorted(expand_dates),
    )


@bp.route("/time/nav")
@login_required
def time_nav():
    user = g.current_user
    year, month = _parse_ym()
    direction = request.args.get("dir", "")
    time_svc = current_app.config["TIME_SVC"]
    year, month = time_svc.clamp_month(user, year, month)

    if direction == "prev":
        year, month = prev_month(year, month)
        year, month = time_svc.clamp_month(user, year, month)
    elif direction == "next":
        if time_svc.can_navigate_next(user, year, month):
            year, month = next_month(year, month)

    return redirect(url_for("time.time_entry", year=year, month=month))


@bp.route("/time/expand")
@login_required
def time_expand():
    year, month = _parse_ym()
    expand_date = request.args.get("date", "")
    existing = request.args.getlist("expand")
    if expand_date and expand_date not in existing:
        existing.append(expand_date)
    return redirect(
        url_for("time.time_entry", year=year, month=month, expand=existing)
    )


@bp.route("/time/save", methods=["POST"])
@login_required
def time_save():
    err = require_csrf()
    if err:
        flash(err, "error")
        return redirect(url_for("time.time_entry"))

    user = g.current_user
    try:
        year = int(request.form.get("year", 0))
        month = int(request.form.get("month", 0))
    except ValueError:
        flash("Invalid month", "error")
        return redirect(url_for("time.time_entry"))

    # Parse repeated form fields: dates[], from[], to[], desc[], sort[]
    dates = request.form.getlist("entry_date")
    froms = request.form.getlist("time_from")
    tos = request.form.getlist("time_to")
    descs = request.form.getlist("description")
    sorts = request.form.getlist("sort_order")

    rows = []
    for i, d in enumerate(dates):
        rows.append(
            {
                "entry_date": d,
                "time_from": froms[i] if i < len(froms) else "",
                "time_to": tos[i] if i < len(tos) else "",
                "description": descs[i] if i < len(descs) else "",
                "sort_order": sorts[i] if i < len(sorts) else i,
            }
        )

    time_svc = current_app.config["TIME_SVC"]
    error = time_svc.save_month_entries(user, year, month, rows)
    if error:
        flash(error, "error")
    else:
        flash("Zeiteinträge gespeichert.", "success")

    expand = request.form.getlist("expand")
    return redirect(url_for("time.time_entry", year=year, month=month, expand=expand))


@bp.route("/time/close", methods=["POST"])
@login_required
def time_close():
    err = require_csrf()
    if err:
        flash(err, "error")
        return redirect(url_for("time.time_entry"))

    user = g.current_user
    year = int(request.form.get("year"))
    month = int(request.form.get("month"))
    action = request.form.get("action", "close")
    time_svc = current_app.config["TIME_SVC"]
    time_svc.set_month_closed(user, year, month, closed=(action == "close"))
    flash(
        "Monat abgeschlossen." if action == "close" else "Monat wieder geöffnet.",
        "success",
    )
    return redirect(url_for("time.time_entry", year=year, month=month))
