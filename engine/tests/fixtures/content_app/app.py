# Public content rule (docs/03-detection-rules.md, part 6), used by test_public_content.py.
# The engine never runs this code. The comment above each route says whether
# it is public content (not flagged) or must still be flagged, and why.
from flask import Flask, g, jsonify, make_response, render_template, request, session
from flask_login import current_user

app = Flask(__name__)


# --- public content: not flagged -------------------------------------------

# public: a constant string
@app.route("/news")
def news():
    return "<h1>News</h1><p>We opened a new shop.</p>"


# public: bytes
@app.get("/robots.txt")
def robots():
    return b"User-agent: *"


# public: an f-string without placeholders, after a docstring
@app.route("/hours", methods=["GET", "HEAD"])
def hours():
    """Opening hours."""
    return f"Open 9 to 5"


# public: jsonify of a dict of constants
@app.route("/api/info")
def api_info():
    return jsonify({"name": "Shop", "version": 1, "tags": ["a", "b"]})


# public: a template with no Jinja at all
@app.route("/terms")
def terms():
    return render_template("terms.html")


# public: a template that only extends, uses blocks and includes, with a constant keyword
@app.route("/faq")
def faq():
    return render_template("faq.html", title="FAQ", logo=url_for("static", filename="logo.png"))


# public: make_response around a constant
@app.route("/help")
def help_page():
    return make_response("Read the FAQ.")


# --- must still be flagged ---------------------------------------------------

# flagged: reads request.args
@app.route("/search")
def search():
    return "You searched for " + request.args.get("q", "")


# flagged: uses the session
@app.route("/greeting")
def greeting():
    return session.get("name", "guest")


# flagged: uses current_user
@app.route("/whoami")
def whoami():
    return current_user.name


# flagged: uses g
@app.route("/theme")
def theme():
    return g.theme


# flagged: calls the database
@app.route("/products")
def products():
    return str(db.execute("SELECT * FROM products").fetchall())


# flagged: accepts POST
@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    return "Thanks"


# flagged: the path has a URL variable
@app.route("/news/<int:news_id>")
def news_item(news_id):
    return "A news item"


# flagged: an f-string with a variable
@app.route("/version")
def version():
    return f"Version {VERSION}"


# flagged: constant text that contains "secret"
@app.route("/club")
def club():
    return "The secret door is on the left."


# flagged: constant page at a path with "admin"
@app.route("/admin/info")
def admin_info():
    return "Just an info page"


# flagged: handler name with a privileged word
@app.route("/report")
def export_report():
    return "Report"


# flagged: an extra decorator that is not a route decorator
@app.route("/cached")
@cache.cached(timeout=60)
def cached():
    return "Cached page"


# flagged: calls a function of the project
@app.route("/prices")
def prices():
    return load_prices()


# flagged: more than a single return
@app.route("/motd")
def motd():
    message = "Hello"
    return message


# flagged: the template has a {{ }} expression
@app.route("/hello")
def hello():
    return render_template("hello.html")


# flagged: the template has an {% if %} statement
@app.route("/menu")
def menu():
    return render_template("menu.html")


# flagged: the template extends one with a {{ }} expression
@app.route("/child")
def child():
    return render_template("child.html")


# flagged: the template file does not exist
@app.route("/missing")
def missing():
    return render_template("missing.html")


# flagged: the template contains "API_KEY"
@app.route("/keys")
def keys():
    return render_template("keys.html")


# flagged: a keyword argument that is not constant
@app.route("/welcome")
def welcome():
    return render_template("terms.html", name=NAME)


# flagged: jsonify of something that is not a dict of constants
@app.route("/api/stats")
def api_stats():
    return jsonify(STATS)
