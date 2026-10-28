# Session checks that do and do not stop a visitor, used by test_protections.py.
# The engine never runs this code. A session check counts only when it can turn
# the visitor away (docs/03-detection-rules.md, part 2d).
from flask import Flask, abort, redirect, session

app = Flask(__name__)


# none: the user id is only read, with user 1 as the default (like corpus app 1's /checkout)
@app.route("/checkout", methods=["POST"])
def checkout():
    user_id = session.get("user_id", 1)
    return "order placed for " + str(user_id)


# none: both branches show a page, so nobody is turned away (like corpus app 1's /orders)
@app.route("/orders")
def orders():
    if "user_id" in session:
        shown = "your orders"
    else:
        shown = "all orders"
    return shown


# inline:session_user_check  (an error answer with status 401)
@app.route("/inbox")
def inbox():
    if "user_id" not in session:
        return "please log in", 401
    return "inbox"


# inline:session_user_check  (the redirect is in the else branch, and goes to "/")
@app.route("/settings")
def settings():
    if session.get("user_id"):
        return "settings"
    else:
        return redirect("/")


# inline:session_user_check  (raise stops the request too)
@app.route("/billing")
def billing():
    if not session.get("user"):
        raise PermissionError("not logged in")
    return "billing"


# none: the if turns the visitor away, but it tests "theme", which is not a user key
@app.route("/theme")
def theme():
    if session.get("theme") is None:
        return redirect("/")
    return "theme"
