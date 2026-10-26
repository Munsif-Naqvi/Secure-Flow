# An app-wide hook that skips some pages, used by test_protections.py.
# The engine never runs this code. Which pages are skipped depends on
# request.endpoint, so every route gets "before_request_partial".
from flask import Flask, redirect, request, session, url_for

app = Flask(__name__)

PUBLIC_PAGES = ["login", "static"]


@app.before_request
def require_login():
    if request.endpoint in PUBLIC_PAGES:
        return None
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return None


# before_request_partial
@app.route("/login", methods=["GET", "POST"])
def login():
    return "login form"


# before_request_partial
@app.route("/notes")
def notes():
    return "notes"
