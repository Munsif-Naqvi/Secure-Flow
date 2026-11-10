"""Fixture for the missing-ownership-check rule (docs/03-detection-rules.md, part 10).

The comment above each route says whether it should be flagged as
missing_ownership_check and why. The engine never runs this code.
"""
import sqlite3
from functools import wraps

from flask import Flask, abort, redirect, request, session, url_for
from flask_login import current_user, login_required

app = Flask(__name__)


def get_db():
    return sqlite3.connect("fixture.db")


def init_db():
    db = get_db()
    db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, email TEXT)")
    db.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            body TEXT
        )
    """)
    db.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL)")
    db.execute("""CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY, title TEXT, writer INTEGER,
        FOREIGN KEY (writer) REFERENCES users(id))""")
    # Shared table: no owner column, so its rows are not private.
    db.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT, price DECIMAL(10, 2))")


def owner_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)
    return wrapper


# FLAGGED: the note id comes from the query string, no ownership check.
@app.route("/notes/view")
@login_required
def view_note():
    note_id = request.args.get("id")
    return str(get_db().execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone())


# FLAGGED: the note id is a URL variable.
@app.route("/notes/<int:note_id>")
@login_required
def show_note(note_id):
    return str(get_db().execute("SELECT body FROM notes WHERE id = ?", (note_id,)).fetchone())


# FLAGGED: deletes any note by its id (changes data).
@app.route("/notes/<int:note_id>/delete", methods=["POST"])
@login_required
def delete_note(note_id):
    get_db().execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return redirect(url_for("view_note"))


# FLAGGED: the visitor's id is only a default; ?id=2 still opens user 2.
@app.route("/profile")
@login_required
def profile():
    user_id = request.args.get("id")
    if not user_id:
        user_id = session["user_id"]
    return str(get_db().execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone())


# FLAGGED: the id goes into an f-string query (orders has a customer_id column).
@app.route("/orders/<order_id>")
@login_required
def show_order(order_id):
    return str(get_db().execute(f"SELECT * FROM orders WHERE id = {order_id}").fetchone())


# FLAGGED: invoices belong to users through "owner ... REFERENCES users(id)" in schema.sql.
@app.route("/invoices/view")
@login_required
def view_invoice():
    invoice_id = int(request.args["invoice"])
    return str(get_db().execute("SELECT total FROM invoices WHERE id = ?", (invoice_id,)).fetchone())


# FLAGGED: the post id comes from the JSON body; posts belong to users through a FOREIGN KEY.
@app.route("/api/posts/rename", methods=["POST"])
@login_required
def rename_post():
    data = request.get_json()
    get_db().execute("UPDATE posts SET title = ? WHERE id = ?", (data["title"], data["id"]))
    return "ok"


# FLAGGED: comparing the session with None is a login check, not an ownership check.
@app.route("/notes/raw")
@login_required
def raw_note():
    if session.get("user_id") is None:
        return redirect(url_for("login"))
    sql = "SELECT body FROM notes WHERE id = ?"
    return str(get_db().execute(sql, (request.form["id"],)).fetchone())


# NOT FLAGGED: the note's owner is compared with the session user.
@app.route("/notes/checked")
@login_required
def checked_note():
    note = get_db().execute("SELECT * FROM notes WHERE id = ?", (request.args.get("id"),)).fetchone()
    if note["user_id"] != session["user_id"]:
        abort(403)
    return str(note)


# NOT FLAGGED: same, with current_user and an error answer.
@app.route("/notes/<int:note_id>/edit", methods=["POST"])
@login_required
def edit_note(note_id):
    note = get_db().execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if note["user_id"] != current_user.id:
        return "Not your note", 403
    return "saved"


# NOT FLAGGED: the query itself is tied to the logged-in user.
@app.route("/notes/mine/<int:note_id>")
@login_required
def my_note(note_id):
    return str(get_db().execute("SELECT * FROM notes WHERE id = ? AND user_id = ?",
                                (note_id, session["user_id"])).fetchone())


# NOT FLAGGED: tied to the user through a variable.
@app.route("/orders/mine/<int:order_id>")
@login_required
def my_order(order_id):
    customer = current_user.id
    return str(get_db().execute("SELECT * FROM orders WHERE id = ? AND customer_id = ?",
                                (order_id, customer)).fetchone())


# NOT FLAGGED: products are shared, not owned by users.
@app.route("/products/<int:product_id>")
@login_required
def product(product_id):
    return str(get_db().execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone())


# NOT FLAGGED: no CREATE TABLE for "gadgets" was found, so SecureFlow cannot tell who owns it.
@app.route("/gadgets/<int:gadget_id>")
@login_required
def gadget(gadget_id):
    return str(get_db().execute("SELECT * FROM gadgets WHERE id = ?", (gadget_id,)).fetchone())


# NOT FLAGGED: INSERT adds a new row; it does not open someone else's.
@app.route("/notes/new", methods=["POST"])
@login_required
def new_note():
    get_db().execute("INSERT INTO notes (user_id, body) VALUES (?, ?)", (session["user_id"], request.form["body"]))
    return "ok"


# NOT FLAGGED: the visitor chooses nothing; the id comes from the session.
@app.route("/me")
@login_required
def me():
    return str(get_db().execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone())


# NOT FLAGGED: an owner-style decorator is trusted as an ownership check.
@app.route("/notes/<int:note_id>/share")
@login_required
@owner_required
def share_note(note_id):
    return str(get_db().execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone())


# NOT FLAGGED as ownership: no login check, so it is a missing_login finding only.
@app.route("/notes/open/<int:note_id>")
def open_note(note_id):
    return str(get_db().execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone())
