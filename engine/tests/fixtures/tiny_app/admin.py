# Blueprint-wide hooks, used by test_protections.py. The engine never runs this code.
import logging

from flask import Blueprint, abort
from flask_login import current_user

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


# This hook runs before every admin_bp route and checks the login,
# so every admin_bp route gets "before_request".
@admin_bp.before_request
def require_admin_login():
    if not current_user.is_authenticated:
        abort(401)


# before_request
@admin_bp.route("/users")
def admin_users():
    return "users"


# before_request
@admin_bp.post("/users/<int:user_id>/delete")
def admin_delete_user(user_id):
    return "deleted"


# This hook only writes a log line. It checks nothing, so it is not a protection.
@reports_bp.before_request
def log_report_request():
    logging.info("report requested")


# none
@reports_bp.route("/sales")
def sales():
    return "sales"
