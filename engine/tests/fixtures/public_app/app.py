# Public allowlist and misplaced login decorators, used by test_rules.py.
# The engine never runs this code. The comment above each route says
# whether the missing-login rule should flag it.
from flask import Flask
from flask_login import login_required
from security import roles_required

app = Flask(__name__)


# not flagged: "/About/" is "/about" once lowercased without the trailing slash
@app.route("/About/")
def about_page():
    return "about"


# not flagged: everything under /static/ is public
@app.route("/static/<path:filename>")
def files(filename):
    return filename


# not flagged: the handler is called "login", which is on the allowlist
@app.route("/sign-in-here", methods=["GET", "POST"])
def login():
    return "login form"


# flagged (Medium): open, and neither the path nor the name is public
@app.route("/profile")
def profile():
    return "profile"


# flagged (High): a POST route can change data
@app.post("/comments")
def add_comment():
    return "added"


# flagged (High): the path contains "admin"
@app.route("/site-admin")
def site_admin():
    return "admin"


# flagged even though "/home" is public: the @login_required above the route
# shows a login check was wanted, but Flask ignores it in this position.
@login_required
@app.route("/home")
def home():
    return "home"


# flagged, and the explanation names both misplaced decorators
@login_required
@roles_required("admin")
@app.route("/reports")
def reports():
    return "reports"


# not flagged: protected by the @login_required below the route decorator
# (the one above is still ignored by Flask, but this route has a check)
@login_required
@app.route("/settings")
@login_required
def settings():
    return "settings"
