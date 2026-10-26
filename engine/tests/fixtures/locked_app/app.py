# An app-wide hook with a login check and no exceptions, used by
# test_protections.py. The engine never runs this code.
from flask import Blueprint, Flask, session, abort

app = Flask(__name__)
api_bp = Blueprint("api", __name__, url_prefix="/api")


@app.before_request
def require_login():
    if "user_id" not in session:
        abort(401)


# before_request  (the app's own route)
@app.route("/dashboard")
def dashboard():
    return "dashboard"


# before_request  (an app hook runs for Blueprint routes too)
@api_bp.get("/data")
def data():
    return "data"


app.register_blueprint(api_bp)
