# Tiny sample used by test_routes.py. The engine never runs this code.
# Each route's expected result is in the comment above it.
from flask import Flask
from flask.views import MethodView

from shop import shop_bp
from shop.api import api_bp

app = Flask(__name__)
app.register_blueprint(shop_bp, url_prefix="/shop")
app.register_blueprint(api_bp)

ITEMS_URL = "/items"


# GET /
@app.route("/")
def index():
    return "Home"


# GET, POST /items  (path read from the ITEMS_URL constant)
@app.route(ITEMS_URL, methods=["get", "POST"])
def items():
    return "Items"


# GET /status, POST /submit, PUT /item/<id>, DELETE /item/<id>, PATCH /item/<id>
@app.get("/status")
def status():
    return "ok"


@app.post("/submit")
def submit():
    return "sent"


@app.put("/item/<int:item_id>")
def replace_item(item_id):
    return "replaced"


@app.delete("/item/<int:item_id>")
def delete_item(item_id):
    return "deleted"


@app.patch("/item/<int:item_id>")
def update_item(item_id):
    return "updated"


# Two decorators on one function: two routes, GET /a and GET /b
@app.route("/a")
@app.route("/b")
def two_urls():
    return "a or b"


def about():
    return "About"


# GET /about
app.add_url_rule("/about", view_func=about)


def contact():
    return "Contact"


# GET, POST /contact  (handler as the third positional argument)
app.add_url_rule("/contact", "contact", contact, methods=["GET", "POST"])


class ProfileView(MethodView):
    def get(self):
        return "profile"

    def post(self):
        return "saved"


# GET, POST /profile  (methods come from the MethodView class)
app.add_url_rule("/profile", view_func=ProfileView.as_view("profile"))


# Not reported: the URL is built at run time, so it cannot be read from the code.
def make_url():
    return "/dynamic"


@app.route(make_url())
def dynamic():
    return "dynamic"


# Not reported: `cache` is not a Flask app or Blueprint.
@cache.route("/not-a-route")
def not_a_route():
    return "no"
