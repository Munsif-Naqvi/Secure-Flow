# Routes for the shop Blueprint, which is defined in shop/__init__.py.
from . import shop_bp


# GET /shop/  (prefix "/shop" + "/")
@shop_bp.route("/")
def shop_home():
    return str(db.execute("SELECT * FROM products").fetchall())  # reads the database: not public content


# GET, DELETE /shop/orders/<int:order_id>
@shop_bp.route("/orders/<int:order_id>", methods=("GET", "DELETE"))
def order(order_id):
    return "order"


def cart():
    return "cart"


# POST /shop/cart  (add_url_rule on a Blueprint also gets the prefix)
shop_bp.add_url_rule("/cart", view_func=cart, methods=["POST"])
