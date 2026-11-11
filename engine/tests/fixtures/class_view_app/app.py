from flask import Flask
from flask_smorest import Api

from resources import blp

app = Flask(__name__)
api = Api(app)
api.register_blueprint(blp)
