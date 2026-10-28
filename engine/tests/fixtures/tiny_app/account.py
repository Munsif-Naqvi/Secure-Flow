# Routes with and without login protections, used by test_protections.py.
# The engine never runs this code. Each route's expected protections_found
# is in the comment above it ("none" means an empty list).
from flask import Blueprint, abort, redirect, request, session, url_for
from flask.views import MethodView
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_login import current_user, login_required

import auth
from cache import cache
from security import check_admin_rights, roles_required

account_bp = Blueprint("account", __name__, url_prefix="/account")


# login_required
@account_bp.route("/settings")
@login_required
def settings():
    return "settings"


# jwt_required  (the called form @jwt_required())
@account_bp.post("/token")
@jwt_required()
def refresh_token():
    return "token"


# login_required  (dotted name: only the last part is compared)
@account_bp.route("/billing")
@auth.login_required
def billing():
    return "billing"


# roles_required, custom_decorator:check_admin_rights  (two decorators, in order)
@account_bp.route("/staff", methods=["GET", "POST"])
@roles_required("admin")
@check_admin_rights
def staff():
    return "staff"


# none: @login_required is ABOVE the route decorator. Python applies
# decorators from the bottom up, so Flask saved the plain function before
# login_required wrapped it. The live route has no login check.
@login_required
@account_bp.route("/export")
def export():
    return "export"


# none: a decorator that has nothing to do with login
@account_bp.route("/news")
@cache.cached(timeout=60)
def news():
    return "news"


# inline:current_user.is_authenticated, inline:abort_401
@account_bp.route("/orders")
def orders():
    if not current_user.is_authenticated:
        abort(401)
    return "orders"


# inline:login_redirect, inline:session_user_check
@account_bp.route("/cart", methods=["POST"])
def cart():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return "cart"


# inline:login_redirect  ("logged_in" is not a user key, but the redirect counts)
@account_bp.route("/wishlist")
def wishlist():
    if not session.get("logged_in"):
        return redirect("/login")
    return "wishlist"


# none: session["user"] is only read; nothing turns the visitor away
@account_bp.route("/me")
def me():
    return "hello " + session["user"]


# inline:abort_403
@account_bp.delete("/close")
def close_account():
    if request.form.get("confirm") != "yes":
        abort(403)
    return "closed"


# inline:authorization_header  (through a variable that is tested in an if)
@account_bp.route("/api-key")
def api_key():
    token = request.headers.get("Authorization")
    if token is None:
        return "missing", 400
    return "key"


# inline:get_jwt_identity
@account_bp.route("/whoami")
def whoami():
    return get_jwt_identity()


# none: abort(404) means "not found", not "not logged in";
# and "theme" is not a user key in the session.
@account_bp.route("/theme")
def theme():
    if session.get("theme") is None:
        abort(404)
    return session["theme"]


class AddressView(MethodView):
    decorators = [login_required]

    def get(self):
        return "addresses"


# login_required  (from the MethodView decorators list)
account_bp.add_url_rule("/addresses", view_func=AddressView.as_view("addresses"))


@login_required
def avatar():
    return "avatar"


# login_required  (add_url_rule gets the function with all its decorators applied)
account_bp.add_url_rule("/avatar", view_func=avatar)
