# Blueprint with no url_prefix of its own. app.py registers it with "/shop".
from flask import Blueprint

shop_bp = Blueprint("shop", __name__)

from . import views  # noqa: E402,F401  (the usual Flask pattern)
