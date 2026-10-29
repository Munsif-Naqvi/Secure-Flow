# Privileged words and neighbour consistency (docs/03-detection-rules.md, part 7),
# used by test_signals.py. The engine never runs this code. The comment above
# each route gives the expected severity and why.
from flask import Blueprint, Flask, request
from flask_login import login_required

app = Flask(__name__)
orders_bp = Blueprint("orders", __name__, url_prefix="/orders")
notes_bp = Blueprint("notes", __name__, url_prefix="/notes")
app.register_blueprint(orders_bp)
app.register_blueprint(notes_bp)


# --- Blueprint "orders": 3 protected routes and 1 unprotected -----------------

# protected
@orders_bp.route("/")
@login_required
def list_orders():
    return str(db.execute("SELECT * FROM orders").fetchall())


# protected
@orders_bp.route("/<int:order_id>")
@login_required
def show_order(order_id):
    return str(order_id)


# protected
@orders_bp.route("/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel_order(order_id):
    return "cancelled"


# High: 3 of 3 other routes in the Blueprint are protected
@orders_bp.route("/<int:order_id>/invoice")
def order_invoice(order_id):
    return str(order_id)


# --- Blueprint "notes": 1 protected of 3, below 60% ---------------------------

# protected
@notes_bp.route("/mine")
@login_required
def my_notes():
    return "notes"


# Medium: only 1 of the 3 routes is protected
@notes_bp.route("/recent")
def recent_notes():
    return request.args.get("n", "")


# Medium: same group as /notes/recent
@notes_bp.route("/popular")
def popular_notes():
    return request.args.get("n", "")


# --- path group "help" (no Blueprint): public content is not counted --------

# protected
@app.route("/help/tickets")
@login_required
def help_tickets():
    return "tickets"


# protected
@app.route("/help/chat")
@login_required
def help_chat():
    return "chat"


# public content: fixed text, not counted in the group
@app.route("/help/faq")
def help_faq():
    return "Read the manual."


# High: 2 of 2 other counted routes are protected (the FAQ is not counted)
@app.route("/help/search")
def help_search():
    return request.args.get("q", "")


# --- a group too small to count ---------------------------------------------

# protected
@app.route("/team/roster")
@login_required
def team_roster():
    return "roster"


# Medium: the group "team" has only 2 routes
@app.route("/team/calendar")
def team_calendar():
    return request.args.get("month", "")


# --- privileged words and Flask path syntax ---------------------------------

# High: "export" in the path; the path keeps Flask's <int:id> syntax
@app.route("/<int:id>/export")
def item_file(id):
    return str(id)


# Medium: a URL variable but no signal
@app.route("/<int:id>/view")
def item_view(id):
    return str(id)


# High: "dump" in the handler name
@app.route("/stats")
def dump_stats():
    return request.args.get("q", "")


# Medium: no signal at all
@app.route("/weather")
def weather():
    return request.args.get("city", "")
