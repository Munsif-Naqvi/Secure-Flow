"""Fixture for the missing-role-check rule (docs/03-detection-rules.md, part 9).

The comment above each route says whether it should be flagged as
missing_role_check and why. The engine never runs this code.
"""
from functools import wraps

from flask import Blueprint, Flask, abort, redirect, session, url_for
from flask_login import current_user, login_required

app = Flask(__name__)
staff_bp = Blueprint("staff", __name__, url_prefix="/staff")
admin_bp = Blueprint("admin_tools", __name__, url_prefix="/tools")


def admin_only(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return wrapper


# FLAGGED: logged in, admin path, no role check.
@app.route("/admin/settings")
@login_required
def admin_settings():
    return "settings"


# FLAGGED: logged in, "admin" in the handler name, no role check.
@app.route("/panel")
@login_required
def admin_panel():
    return "panel"


# FLAGGED: the role is only read, never used to turn anyone away.
@app.route("/admin/stats")
@login_required
def admin_stats():
    role = session.get("role")
    return "stats for " + str(role)


# not flagged: inline role check that aborts.
@app.route("/admin/users")
@login_required
def admin_users():
    if session.get("role") != "admin":
        abort(403)
    return "users"


# not flagged: role check through current_user, returning 403.
@app.route("/admin/logs")
@login_required
def admin_logs():
    if not current_user.is_admin:
        return "Forbidden", 403
    return "logs"


# not flagged: has_role(...) check that redirects.
@app.route("/admin/backup")
@login_required
def admin_backup():
    if not current_user.has_role("admin"):
        return redirect(url_for("index"))
    return "backup"


# not flagged: home-made role decorator ("admin" in its name).
@app.route("/admin/reports")
@login_required
@admin_only
def admin_reports():
    return "reports"


# not flagged: a known role decorator from Flask-Security.
@app.route("/admin/roles")
@login_required
@roles_required("admin")
def admin_roles():
    return "roles"


# FLAGGED: @admin_only sits ABOVE the route decorator, so Flask ignores it.
@admin_only
@app.route("/admin/purge")
@login_required
def admin_purge():
    return "purged"


# not flagged here: no login check at all. The missing-login rule flags it instead.
@app.route("/admin/open")
def admin_open():
    return "open"


# not flagged: logged in, but nothing in the name says "admin".
@app.route("/dashboard")
@login_required
def dashboard():
    return "dashboard"


# The staff Blueprint's hook checks the role, so its routes are covered.
@staff_bp.before_request
def staff_must_be_admin():
    if session.get("role") != "admin":
        abort(403)


# not flagged: covered by the Blueprint's role hook.
@staff_bp.route("/admin/rota")
@login_required
def staff_rota():
    return "rota"


# FLAGGED: "admin" is in the Blueprint's variable name, and nothing checks the role.
@admin_bp.route("/cleanup")
@login_required
def cleanup():
    return "cleanup"


app.register_blueprint(staff_bp)
app.register_blueprint(admin_bp)
