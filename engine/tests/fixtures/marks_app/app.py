"""Fixture for routes the developer marks as public (docs/03-detection-rules.md, part 8).

The comment above each route says whether it should be flagged and why.
None of these routes is protected, and none returns fixed content, so
without a mark every one of them would be flagged.
"""
from flask import Flask, jsonify
from flask_login import login_required

app = Flask(__name__)
db = None


# Marked by comment: not flagged.
# secureflow: public
@app.route("/catalog")
def catalog():
    return jsonify(db.execute("SELECT name FROM products").fetchall())


# Marked by comment above a stack of two decorators: both routes are marked.
#   SecureFlow:   PUBLIC
@app.route("/prices")
@app.route("/prices/today")
def prices():
    return jsonify(db.execute("SELECT * FROM prices").fetchall())


# secureflow: public

# Not marked: a blank line separates the comment from the route. Flagged.
@app.route("/stock")
def stock():
    return jsonify(db.execute("SELECT * FROM stock").fetchall())


# Not marked: the comment sits between the decorator and the function. Flagged.
@app.route("/offers")
# secureflow: public
def offers():
    return jsonify(db.execute("SELECT * FROM offers").fetchall())


# Marked, but @login_required sits above the route decorator, so Flask
# ignores it. The two contradict each other: flagged.
# secureflow: public
@login_required
@app.route("/wishlist")
def wishlist():
    return jsonify(db.execute("SELECT * FROM wishlist").fetchall())


# Marked in .secureflow/route_decisions.json as "/news": not flagged.
@app.route("/news/")
def news():
    return jsonify(db.execute("SELECT * FROM news").fetchall())


# Matches "/shop/*" in the decisions file: not flagged.
@app.route("/shop/<int:item_id>")
def shop_item(item_id):
    return jsonify(db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone())


# "/shop/*" matches one part only, so this route is flagged.
@app.route("/shop/<int:item_id>/reviews")
def shop_reviews(item_id):
    return jsonify(db.execute("SELECT * FROM reviews WHERE item = ?", (item_id,)).fetchall())


# Matching is case-sensitive, as in Flask: "/News" is not "/news". Flagged.
@app.route("/News/archive")
def news_archive():
    return jsonify(db.execute("SELECT * FROM news").fetchall())


# Marked by comment above add_url_rule: not flagged.
def opening_hours():
    return jsonify(db.execute("SELECT * FROM hours").fetchall())


# secureflow: public
app.add_url_rule("/hours", view_func=opening_hours)
