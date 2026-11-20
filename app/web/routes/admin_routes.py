"""Admin: Chronos management and user administration."""

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

from app.logger import log
from app.security import hash_password, validate_password, validate_username
from app.services.time_utils import is_real_calendar_day, parse_decimal
from app.web.helpers import admin_required, clear_session_cookie, require_csrf

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _render_chronos(edit, special_days, form_name, form_daily, field_errors=None):
    repo = current_app.config["CHRONOS_REPO"]
    return render_template(
        "admin/chronos.html",
        user=g.current_user,
        items=repo.list_all(),
        edit=edit,
        special_days=special_days,
        form_name=form_name,
        form_daily=form_daily,
        field_errors=field_errors or {},
        csrf_token=g.csrf_token,
        active_nav="admin_chronos",
    )


def _db_special_rows(days) -> list[dict]:
    return [
        {
            "day": sd.day,
            "month": sd.month,
            "year": "" if sd.year is None else sd.year,
            "target": f"{sd.target_hours:.1f}",
            "description": sd.description,
            "error": "",
        }
        for sd in days
    ]


def _posted_special_rows() -> list[dict]:
    months = request.form.getlist("sd_month")
    days = request.form.getlist("sd_day")
    years = request.form.getlist("sd_year")
    targets = request.form.getlist("sd_target")
    descs = request.form.getlist("sd_description")
    count = max(len(months), len(days), len(years), len(targets), len(descs), 0)
    rows = []
    for i in range(count):
        rows.append(
            {
                "day": days[i] if i < len(days) else "",
                "month": months[i] if i < len(months) else "",
                "year": years[i] if i < len(years) else "",
                "target": targets[i] if i < len(targets) else "",
                "description": descs[i] if i < len(descs) else "",
                "error": "",
            }
        )
    return rows


def _special_row_blank(row: dict) -> bool:
    return not any(str(row[key]).strip() for key in ("day", "month", "year", "target", "description"))


@bp.route("/chronos")
@admin_required
def chronos_list():
    return _render_chronos(None, [], "", "8.0")


@bp.route("/chronos/edit/<int:chronos_id>")
@admin_required
def chronos_edit(chronos_id: int):
    repo = current_app.config["CHRONOS_REPO"]
    edit = repo.get(chronos_id)
    if not edit:
        flash("Chronos nicht gefunden.", "error")
        return redirect(url_for("admin.chronos_list"))
    return _render_chronos(
        edit,
        _db_special_rows(repo.list_special_days(chronos_id)),
        edit.name,
        f"{edit.daily_target_hours:.1f}",
    )


@bp.route("/chronos/save", methods=["POST"])
@admin_required
def chronos_save():
    repo = current_app.config["CHRONOS_REPO"]
    rows = _posted_special_rows()
    name = request.form.get("name") or ""
    daily_raw = request.form.get("daily_target_hours") if request.form.get("daily_target_hours") is not None else ""
    chronos_id_raw = (request.form.get("chronos_id") or "").strip()
    edit = repo.get(int(chronos_id_raw)) if chronos_id_raw.isdigit() else None

    def fail(message: str, **field_errors):
        flash(message, "error")
        return _render_chronos(edit, rows, name, daily_raw, field_errors)

    err = require_csrf()
    if err:
        return fail(err)

    name_clean = name.strip()
    if not name_clean:
        return fail("Name ist erforderlich.", name="Name ist erforderlich.")
    try:
        daily = parse_decimal(daily_raw.strip() or "0")
    except ValueError:
        return fail("Ungültige Soll-Arbeitszeit.", daily="Ungültige Soll-Arbeitszeit.")
    if daily < 0 or daily > 24:
        return fail(
            "Soll-Arbeitszeit muss zwischen 0 und 24 liegen.",
            daily="Soll-Arbeitszeit muss zwischen 0 und 24 liegen.",
        )

    # Validate every row before writing, and keep the raw values for re-render.
    specials = []
    seen: dict[tuple[int, int, int | None], dict] = {}
    invalid = False
    for row in rows:
        if _special_row_blank(row):
            continue
        try:
            m = int(str(row["month"]).strip())
            d = int(str(row["day"]).strip())
            y_raw = str(row["year"]).strip()
            y = int(y_raw) if y_raw else None
            target_raw = str(row["target"]).strip()
            t = parse_decimal(target_raw or "0")
        except ValueError:
            row["error"] = "Ungültige Spezialtag-Angabe."
            invalid = True
            continue
        if not is_real_calendar_day(m, d, y):
            row["error"] = "Spezialtag: Monat/Tag ungültig."
            invalid = True
            continue
        if y is not None and not (1970 <= y <= 2100):
            row["error"] = "Spezialtag: Jahr ungültig."
            invalid = True
            continue
        if t < 0 or t > 24:
            row["error"] = "Soll-Arbeitszeit eines Spezialtags muss zwischen 0 und 24 liegen."
            invalid = True
            continue
        key = (m, d, y)
        if key in seen:
            message = "Spezialtag ist doppelt erfasst."
            row["error"] = message
            if not seen[key]["error"]:
                seen[key]["error"] = message
            invalid = True
            continue
        seen[key] = row
        specials.append(
            {
                "month": m,
                "day": d,
                "year": y,
                "target_hours": t,
                "description": str(row["description"] or "")[:256],
            }
        )

    if invalid:
        return fail("Bitte die markierten Spezialtage korrigieren.")

    if chronos_id_raw:
        if edit is None:
            flash("Chronos nicht gefunden.", "error")
            return redirect(url_for("admin.chronos_list"))
        repo.update(edit.id, name_clean, daily)
        cid = edit.id
    else:
        created = repo.create(name_clean, daily)
        cid = created.id

    repo.replace_special_days(cid, specials)
    flash("Chronos gespeichert.", "success")
    return redirect(url_for("admin.chronos_edit", chronos_id=cid))


@bp.route("/chronos/delete", methods=["POST"])
@admin_required
def chronos_delete():
    err = require_csrf()
    if err:
        flash(err, "error")
        return redirect(url_for("admin.chronos_list"))

    try:
        cid = int(request.form.get("chronos_id") or "")
    except (TypeError, ValueError):
        flash("Chronos nicht gefunden.", "error")
        return redirect(url_for("admin.chronos_list"))
    # Unassign users first
    users = current_app.config["USERS"].list_all()
    for u in users:
        if u.chronos_id == cid:
            current_app.config["USERS"].update_profile(
                u.id,
                u.username,
                u.first_name,
                u.last_name,
                chronos_id=None,
            )
    current_app.config["CHRONOS_REPO"].delete(cid)
    flash("Chronos gelöscht.", "success")
    return redirect(url_for("admin.chronos_list"))


def _empty_create_values() -> dict:
    return {
        "username": "",
        "first_name": "",
        "last_name": "",
        "email": "",
        "is_admin": False,
    }


def _values_from_user(edit) -> dict:
    return {
        "username": edit.username,
        "first_name": edit.first_name,
        "last_name": edit.last_name,
        "email": edit.email,
        "chronos_id": "" if edit.chronos_id is None else str(edit.chronos_id),
        "initial_balance": f"{edit.initial_balance:.1f}",
        "start_year": "" if not edit.start_year else str(edit.start_year),
        "start_month": "" if not edit.start_month else str(edit.start_month),
        "is_admin": bool(edit.is_admin),
        "is_locked": bool(edit.is_locked),
    }


def _posted_user_values() -> dict:
    return {
        "username": request.form.get("username") or "",
        "first_name": request.form.get("first_name") or "",
        "last_name": request.form.get("last_name") or "",
        "email": request.form.get("email") or "",
        "chronos_id": request.form.get("chronos_id") or "",
        "initial_balance": request.form.get("initial_balance") or "",
        "start_year": request.form.get("start_year") or "",
        "start_month": request.form.get("start_month") or "",
        "is_admin": request.form.get("is_admin") == "on",
        "is_locked": request.form.get("is_locked") == "on",
    }


def _posted_create_values() -> dict:
    return {
        "username": request.form.get("username") or "",
        "first_name": request.form.get("first_name") or "",
        "last_name": request.form.get("last_name") or "",
        "email": request.form.get("email") or "",
        "is_admin": request.form.get("is_admin") == "on",
    }


def _render_users(edit=None, values=None, field_errors=None, create_values=None, create_errors=None):
    chronos = current_app.config["CHRONOS_REPO"].list_all()
    return render_template(
        "admin/users.html",
        user=g.current_user,
        users=current_app.config["USERS"].list_all(),
        chronos_map={c.id: c.name for c in chronos},
        edit=edit,
        values=values,
        field_errors=field_errors or {},
        all_chronos=chronos,
        create_values=create_values or _empty_create_values(),
        create_errors=create_errors or {},
        csrf_token=g.csrf_token,
        active_nav="admin_users",
    )


@bp.route("/users")
@admin_required
def users_list():
    return _render_users()


@bp.route("/users/edit/<int:user_id>")
@admin_required
def users_edit(user_id: int):
    edit = current_app.config["USERS"].get_by_id(user_id)
    if not edit:
        flash("Benutzer nicht gefunden.", "error")
        return redirect(url_for("admin.users_list"))
    return _render_users(edit=edit, values=_values_from_user(edit))


@bp.route("/users/save", methods=["POST"])
@admin_required
def users_save():
    users_repo = current_app.config["USERS"]
    try:
        user_id = int(request.form.get("user_id") or "")
    except (TypeError, ValueError):
        flash("Benutzer nicht gefunden.", "error")
        return redirect(url_for("admin.users_list"))
    target = users_repo.get_by_id(user_id)
    if not target:
        flash("Benutzer nicht gefunden.", "error")
        return redirect(url_for("admin.users_list"))

    posted = _posted_user_values()

    def fail(message: str, **errors):
        flash(message, "error")
        return _render_users(edit=target, values=posted, field_errors=errors)

    err = require_csrf()
    if err:
        return fail(err)

    username = posted["username"].strip()
    first_name = posted["first_name"].strip()
    last_name = posted["last_name"].strip()
    email = posted["email"].strip()
    uerr = validate_username(username)
    if uerr:
        return fail(uerr, username=uerr)
    if users_repo.username_exists(username, exclude_id=user_id):
        message = "Benutzername bereits vergeben."
        return fail(message, username=message)
    if not first_name or not last_name or not email:
        message = "Alle Pflichtfelder ausfüllen."
        errors = {}
        if not first_name:
            errors["first_name"] = "Vorname ist erforderlich."
        if not last_name:
            errors["last_name"] = "Nachname ist erforderlich."
        if not email:
            errors["email"] = "E-Mail ist erforderlich."
        return fail(message, **errors)

    is_admin = posted["is_admin"]
    is_locked = posted["is_locked"]

    # Prevent locking yourself out of admin
    if target.id == g.current_user.id and not is_admin:
        message = "Sie können sich nicht selbst die Admin-Rechte entziehen."
        return fail(message, is_admin=message)
    if target.id == g.current_user.id and is_locked:
        message = "Sie können Ihr eigenes Konto nicht sperren."
        return fail(message, is_locked=message)

    new_pw = request.form.get("new_password") or ""
    if new_pw:
        pw_err = validate_password(new_pw)
        if pw_err:
            return fail(pw_err, new_password=pw_err)

    field_errors: dict[str, str] = {}
    start_year = None
    start_month = None
    initial_balance = 0.0
    chronos_id = None
    year_raw = posted["start_year"].strip()
    month_raw = posted["start_month"].strip()
    balance_raw = posted["initial_balance"].strip()
    chronos_raw = posted["chronos_id"].strip()
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
        initial_balance = parse_decimal(balance_raw or "0")
    except ValueError:
        field_errors["initial_balance"] = "Ungültiges Zeitkonto."
    if chronos_raw:
        try:
            chronos_id = int(chronos_raw)
        except ValueError:
            field_errors["chronos_id"] = "Chronos nicht gefunden."
        else:
            if current_app.config["CHRONOS_REPO"].get(chronos_id) is None:
                field_errors["chronos_id"] = "Chronos nicht gefunden."
    if field_errors:
        message = next(iter(field_errors.values()))
        flash(message, "error")
        return _render_users(edit=target, values=posted, field_errors=field_errors)

    users_repo.update_profile(
        user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        chronos_id=chronos_id,
        start_year=start_year,
        start_month=start_month,
        initial_balance=initial_balance,
        is_admin=is_admin,
        is_locked=is_locked,
    )

    if new_pw:
        pw_err = current_app.config["AUTH"].admin_reset_password(user_id, new_pw)
        if pw_err:
            flash(pw_err, "error")
            return redirect(url_for("admin.users_edit", user_id=user_id))
        if user_id == g.current_user.id:
            flash("Passwort geändert. Bitte melden Sie sich erneut an.", "success")
            resp = make_response(redirect(url_for("auth.login")))
            return clear_session_cookie(resp)
        flash("Benutzer gespeichert und Passwort zurückgesetzt.", "success")
    else:
        flash("Benutzer gespeichert.", "success")

    if is_locked:
        current_app.config["SESSIONS"].delete_for_user(user_id)

    return redirect(url_for("admin.users_edit", user_id=user_id))


@bp.route("/users/create", methods=["POST"])
@admin_required
def users_create():
    users_repo = current_app.config["USERS"]
    create_values = _posted_create_values()
    return_raw = (request.form.get("return_user_id") or "").strip()
    edit = users_repo.get_by_id(int(return_raw)) if return_raw.isdigit() else None

    def fail(message: str, **errors):
        flash(message, "error")
        return _render_users(
            edit=edit,
            values=_values_from_user(edit) if edit else None,
            create_values=create_values,
            create_errors=errors,
        )

    err = require_csrf()
    if err:
        return fail(err)

    username = create_values["username"].strip()
    first_name = create_values["first_name"].strip()
    last_name = create_values["last_name"].strip()
    email = create_values["email"].strip()
    password = request.form.get("password") or ""

    uerr = validate_username(username)
    if uerr:
        return fail(uerr, username=uerr)
    perr = validate_password(password)
    if perr:
        return fail(perr, password=perr)
    if users_repo.username_exists(username):
        message = "Benutzername bereits vergeben."
        return fail(message, username=message)
    if not first_name or not last_name or not email:
        message = "Alle Pflichtfelder ausfüllen."
        errors = {}
        if not first_name:
            errors["first_name"] = "Vorname ist erforderlich."
        if not last_name:
            errors["last_name"] = "Nachname ist erforderlich."
        if not email:
            errors["email"] = "E-Mail ist erforderlich."
        return fail(message, **errors)

    is_admin = create_values["is_admin"]
    try:
        user = current_app.config["USERS"].create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=hash_password(password),
            is_admin=is_admin,
        )
    except Exception:
        log.exception("Failed to create user %s", username)
        return fail("Benutzer konnte nicht angelegt werden.")
    flash(f"Benutzer {user.username} angelegt.", "success")
    return redirect(url_for("admin.users_edit", user_id=user.id))
