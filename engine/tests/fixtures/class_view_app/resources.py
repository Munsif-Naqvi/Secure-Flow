# Class-based routes in the Flask-Smorest style: `@blp.route` sits on a
# MethodView class, and each method (get, put, delete, ...) answers one HTTP
# method. Every method is its own route, with its own protections.
# (Written for SecureFlow's tests. Never run.)
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask_smorest import Blueprint

blp = Blueprint("Items", __name__, description="Operations on items")


@blp.route("/item/<string:item_id>")
class Item(MethodView):
    # GET /item/<string:item_id>: line 15 (its top decorator), protected by @jwt_required()
    @jwt_required()
    def get(self, item_id):
        return {"id": item_id}

    # DELETE /item/<string:item_id>: line 20, no login check -> flagged
    def delete(self, item_id):
        return {"message": "Item deleted."}

    # PUT /item/<string:item_id>: line 25 (its top decorator), protected by @jwt_required(fresh=True)
    # (@blp.arguments is not a protection, but it does not hide the one below it)
    @blp.arguments(dict)
    @jwt_required(fresh=True)
    def put(self, item_data, item_id):
        return item_data

    # Not an HTTP method name, so not a route.
    def helper(self):
        return None


@blp.route("/store")
class StoreList(MethodView):
    # GET and POST /store: lines 40 and 43, protected by the class `decorators` list
    decorators = [jwt_required()]

    def get(self):
        return []

    def post(self):
        return {}


# A @jwt_required() above @blp.route on a class wraps the class after the
# route was saved, so it protects nothing: GET /admin/stats, line 52 -> flagged, High
@jwt_required()
@blp.route("/admin/stats")
class AdminStats(MethodView):
    def get(self):
        return {"users": 3}
