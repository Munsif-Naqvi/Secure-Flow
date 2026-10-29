"""Corpus regression: run the engine on every app in corpus/ and compare with ground_truth.json.

- every missing_login route in should_flag is still flagged (no recall lost);
- nothing in should_not_flag is flagged;
- every route in known_limitations IS flagged: these are documented limits of
  the code-only scan (for example a public page that reads the database), and
  no rule may be loosened to hide them.
"""

import json
from pathlib import Path

import pytest

from test_main import run_engine

CORPUS = Path(__file__).parent.parent.parent / "corpus"
APPS = sorted(folder for folder in CORPUS.iterdir() if (folder / "ground_truth.json").is_file())


def flagged_routes(result):
    """[(url_path, http_methods)] for every finding, with the methods of its route."""
    methods = {(r["file_path"], r["line_number"], r["url_path"]): r["http_methods"] for r in result["routes"]}
    return [(f["url_path"], methods[(f["file_path"], f["line_number"], f["url_path"])]) for f in result["findings"]]


def is_flagged(entry, flagged):
    """Same matching as score.py: equal path, and a shared method when the entry lists methods."""
    for url_path, methods in flagged:
        if url_path == entry["url_path"] and ("http_methods" not in entry or set(entry["http_methods"]) & set(methods)):
            return True
    return False


@pytest.mark.parametrize("app", APPS, ids=[app.name for app in APPS])
def test_corpus_app_matches_its_ground_truth(app):
    truth = json.loads((app / "ground_truth.json").read_text(encoding="utf-8"))
    flagged = flagged_routes(run_engine(app))

    for entry in truth.get("should_flag", []):
        if entry.get("problem_type", "missing_login") == "missing_login":
            assert is_flagged(entry, flagged), "missed: " + entry["url_path"]
    for entry in truth.get("should_not_flag", []):
        assert not is_flagged(entry, flagged), "false alarm: " + entry["url_path"]
    for entry in truth.get("known_limitations", []):
        assert is_flagged(entry, flagged), "known limitation no longer flagged: " + entry["url_path"]


def test_corpus_has_the_two_new_database_routes():
    app_01 = json.loads((CORPUS / "app_01_ecommerce" / "ground_truth.json").read_text(encoding="utf-8"))
    app_04 = json.loads((CORPUS / "app_04_blog" / "ground_truth.json").read_text(encoding="utf-8"))
    assert [e["url_path"] for e in app_01["known_limitations"]] == ["/catalog"]
    assert "/users" in [e["url_path"] for e in app_04["should_flag"]]


@pytest.mark.parametrize("app, url_path", [
    ("app_01_ecommerce", "/orders/export"),  # "export" in the path and handler name
    ("app_04_blog", "/users"),               # "users" in the path
])
def test_corpus_routes_with_a_privileged_word_are_high(app, url_path):
    findings = [f for f in run_engine(CORPUS / app)["findings"] if f["url_path"] == url_path]
    assert len(findings) == 1
    assert findings[0]["severity"] == "High"
    assert "The name suggests this route handles sensitive data or actions." in findings[0]["explanation"]


def test_corpus_route_without_a_signal_stays_medium():
    # GET /orders in app 1 is open but has no privileged word and no protected neighbours.
    findings = [f for f in run_engine(CORPUS / "app_01_ecommerce")["findings"] if f["url_path"] == "/orders"]
    assert [f["severity"] for f in findings] == ["Medium"]
