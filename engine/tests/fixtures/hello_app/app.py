# Tiny sample used by test_main.py. The engine never runs this code.
from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return "Hello"
