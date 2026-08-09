"""Admin: Chronos management and user administration."""

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

from app.security import hash_password, validate_password, validate_username
from app.web.helpers import admin_required, require_csrf

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/chronos")
@admin_required
def chronos_list():
    repo = current_app.config["CHRONOS_REPO"]
    items = repo.list_all()
    return render_template(
        "admin/chronos.html",
        user=g.current_user,
        items=items,
        edit=None,
        special_days=[],
        csrf_token=g.csrf_token,
        active_nav="admin_chronos",
    )


@bp.route("/chronos/edit/<int:chronos_id>")
@admin_required
def chronos_edit(chronos_id: int):
    repo = current_app.config["CHRONOS_REPO"]
    items = repo.list_all()
    edit = repo.get(chronos_id)
    if not edit:
        flash("Chronos nicht gefunden.", "error")
        return redirect(url_for("admin.chronos_list"))
    special_days = repo.list_special_days(chronos_id)
    return render_template(
        "admin/chronos.html",
        user=g.current_user,
        items=items,
        edit=edit,
        special_days=special_days,
        csrf_token=g.csrf_token,
        active_nav="admin_chronos",
    )


@bp.route("/chronos/save", methods=["POST"])
@admin_required
def chronos_save():
    err = require_csrf()
    if err:
        flash(err, "error")
        return redirect(url_for("admin.chronos_list"))

    repo = current_app.config["CHRONOS_REPO"]
    name = (request.form.get("name") or "").strip()
    try:
        daily = float((request.form.get("daily_target_hours") or "0").replace(",", "."))
    except ValueError:
        flash("Ungültige Soll-Arbeitszeit.", "error")
        return redirect(url_for("admin.chronos_list"))

    if not name:
        flash("Name ist erforderlich.", "error")
        return redirect(url_for("admin.chronos_list"))
    if daily < 0 or daily > 24:
        flash("Soll-Arbeitszeit muss zwischen 0 und 24 liegen.", "error")
        return redirect(url_for("admin.chronos_list"))

    chronos_id_raw = request.form.get("chronos_id") or ""
    if chronos_id_raw:
        cid = int(chronos_id_raw)
        repo.update(cid, name, daily)
    else:
        created = repo.create(name, daily)
        cid = created.id

    # Special days from form arrays
    months = request.form.getlist("sd_month")
    days = request.form.getlist("sd_day")
    years = request.form.getlist("sd_year")
    targets = request.form.getlist("sd_target")
    descs = request.form.getlist("sd_description")

    specials = []
    for i in range(len(months)):
        if not months[i] and not days[i]:
            continue
        try:
            m = int(months[i])
            d = int(days[i])
            y_raw = (years[i] if i < len(years) else "").strip()
            y = int(y_raw) if y_raw else None
            t = float((targets[i] if i < len(targets) else "0").replace(",", "."))
        except ValueError:
            flash("Ungültige Spezialtag-Angabe.", "error")
            return redirect(url_for("admin.chronos_edit", chronos_id=cid))
        if not (1 <= m <= 12 and 1 <= d <= 31):
            flash("Spezialtag: Monat/Tag ungültig.", "error")
            return redirect(url_for("admin.chronos_edit", chronos_id=cid))
        specials.append(
            {
                "month": m,
                "day": d,
                "year": y,
                "target_hours": t,
                "description": descs[i] if i < len(descs) else "",
            }
        )

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

    cid = int(request.form.get("chronos_id"))
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


@bp.route("/users")
@admin_required
def users_list():
    users = current_app.config["USERS"].list_all()
    chronos_map = {c.id: c.name for c in current_app.config["CHRONOS_REPO"].list_all()}
    return render_template(
        "admin/users.html",
        user=g.current_user,
        users=users,
        chronos_map=chronos_map,
        edit=None,
        all_chronos=current_app.config["CHRONOS_REPO"].list_all(),
        csrf_token=g.csrf_token,
        active_nav="admin_users",
    )


@bp.route("/users/edit/<int:user_id>")
@admin_required
def users_edit(user_id: int):
    users_repo = current_app.config["USERS"]
    edit = users_repo.get_by_id(user_id)
    if not edit:
        flash("Benutzer nicht gefunden.", "error")
        return redirect(url_for("admin.users_list"))
    users = users_repo.list_all()
    chronos_map = {c.id: c.name for c in current_app.config["CHRONOS_REPO"].list_all()}
    return render_template(
        "admin/users.html",
        user=g.current_user,
        users=users,
        chronos_map=chronos_map,
        edit=edit,
        all_chronos=current_app.config["CHRONOS_REPO"].list_all(),
        csrf_token=g.csrf_token,
        active_nav="admin_users",
    )


@bp.route("/users/save", methods=["POST"])
@admin_required
def users_save():
    err = require_csrf()
    if err:
        flash(err, "error")
        return redirect(url_for("admin.users_list"))

    users_repo = current_app.config["USERS"]
    user_id = int(request.form.get("user_id"))
    target = users_repo.get_by_id(user_id)
    if not target:
        flash("Benutzer nicht gefunden.", "error")
        return redirect(url_for("admin.users_list"))

    username = (request.form.get("username") or "").strip()
    first_name = (request.form.get("first_name") or "").strip()
    last_name = (request.form.get("last_name") or "").strip()
    email = (request.form.get("email") or "").strip()
    uerr = validate_username(username)
    if uerr:
        flash(uerr, "error")
        return redirect(url_for("admin.users_edit", user_id=user_id))
    if users_repo.username_exists(username, exclude_id=user_id):
        flash("Benutzername bereits vergeben.", "error")
        return redirect(url_for("admin.users_edit", user_id=user_id))

    is_admin = request.form.get("is_admin") == "on"
    is_locked = request.form.get("is_locked") == "on"

    # Prevent locking yourself out of admin
    if target.id == g.current_user.id and not is_admin:
        flash("Sie können sich nicht selbst die Admin-Rechte entziehen.", "error")
        return redirect(url_for("admin.users_edit", user_id=user_id))

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
        return redirect(url_for("admin.users_edit", user_id=user_id))

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

    new_pw = request.form.get("new_password") or ""
    if new_pw:
        pw_err = current_app.config["AUTH"].admin_reset_password(user_id, new_pw)
        if pw_err:
            flash(pw_err, "error")
            return redirect(url_for("admin.users_edit", user_id=user_id))
        flash("Benutzer gespeichert und Passwort zurückgesetzt.", "success")
    else:
        flash("Benutzer gespeichert.", "success")

    if is_locked:
        current_app.config["SESSIONS"].delete_for_user(user_id)

    return redirect(url_for("admin.users_edit", user_id=user_id))


@bp.route("/users/create", methods=["POST"])
@admin_required
def users_create():
    err = require_csrf()
    if err:
        flash(err, "error")
        return redirect(url_for("admin.users_list"))

    username = (request.form.get("username") or "").strip()
    first_name = (request.form.get("first_name") or "").strip()
    last_name = (request.form.get("last_name") or "").strip()
    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""

    uerr = validate_username(username)
    if uerr:
        flash(uerr, "error")
        return redirect(url_for("admin.users_list"))
    perr = validate_password(password)
    if perr:
        flash(perr, "error")
        return redirect(url_for("admin.users_list"))
    if current_app.config["USERS"].username_exists(username):
        flash("Benutzername bereits vergeben.", "error")
        return redirect(url_for("admin.users_list"))
    if not first_name or not last_name or not email:
        flash("Alle Pflichtfelder ausfüllen.", "error")
        return redirect(url_for("admin.users_list"))

    is_admin = request.form.get("is_admin") == "on"
    user = current_app.config["USERS"].create(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        password_hash=hash_password(password),
        is_admin=is_admin,
    )
    flash(f"Benutzer {user.username} angelegt.", "success")
    return redirect(url_for("admin.users_edit", user_id=user.id))
