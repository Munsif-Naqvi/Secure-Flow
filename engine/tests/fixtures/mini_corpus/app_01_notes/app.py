# Practice app for test_score.py: the engine gets every route right here.
from flask import Flask
from flask_login import login_required

app = Flask(__name__)


# Public by design (on the allowlist): not flagged.
@app.route("/")
def home():
    return "Notes"


# Public by design (on the allowlist): not flagged.
@app.route("/login", methods=["GET", "POST"])
def login():
    return "Login"


# Protected: not flagged.
@app.route("/notes")
@login_required
def list_notes():
    return "My notes"


# Unprotected and in should_flag: found.
@app.route("/notes/<int:note_id>/delete", methods=["POST"])
def delete_note(note_id):
    return "Deleted"
