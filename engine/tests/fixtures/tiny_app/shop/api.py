# Blueprint with its own url_prefix, registered in app.py without one.
from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api/")


# GET /api/users
@api_bp.get("/users")
def list_users():
    return "users"


# POST /api/users
@api_bp.post("users")
def create_user():
    return "created"
