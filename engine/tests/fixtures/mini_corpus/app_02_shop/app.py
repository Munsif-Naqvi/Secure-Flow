# Practice app for test_score.py: one of each kind of scoring result.
from flask import Flask

app = Flask(__name__)


def admin_check(view):
    # Looks like a protection because the name contains "admin", but it checks nothing.
    return view


# Public by design (on the allowlist): not flagged.
@app.route("/")
def home():
    return "Shop"


# Public by design but NOT on the allowlist: flagged, so a false alarm ("public by design").
@app.route("/pricing")
def pricing():
    return "Prices"


# Unprotected, but the ground truth does not list it: a false alarm ("not listed").
@app.route("/status")
def status():
    return "OK"


# Unprotected and in should_flag: found.
@app.route("/item/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    return "Deleted"


# Same path, but the ground truth lists only DELETE: a false alarm ("not listed").
@app.route("/item/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    return "Updated"


# The engine trusts @admin_check, so this real problem is missed.
@app.route("/admin/users")
@admin_check
def list_users():
    return "All users"
