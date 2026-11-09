"""Routes the developer marks as public (docs/03-detection-rules.md, part 8).

fixtures/marks_app has one route per case; the comment above each route says
whether it should be flagged and why. Broken decisions files and the
neighbour count are checked with small apps written to a temporary folder.
"""

import json
import textwrap

from schema_check import load_schema, schema_errors
from test_main import FIXTURES, run_engine

RESULT = run_engine(FIXTURES / "marks_app")
FLAGGED = {f["url_path"] for f in RESULT["findings"]}
LABELS = {r["url_path"]: r["protections_found"] for r in RESULT["routes"]}


def test_marked_routes_are_not_flagged_and_keep_a_visible_label():
    assert LABELS["/catalog"] == ["developer_marked:comment"]
    assert LABELS["/hours"] == ["developer_marked:comment"]  # comment above add_url_rule
    assert LABELS["/news/"] == ["developer_marked:decisions_file"]  # trailing slash ignored
    assert LABELS["/shop/<int:item_id>"] == ["developer_marked:decisions_file"]  # "*" wildcard
    for path in ["/catalog", "/hours", "/news/", "/shop/<int:item_id>"]:
        assert path not in FLAGGED, path


def test_one_comment_marks_every_route_on_the_function():
    assert LABELS["/prices"] == LABELS["/prices/today"] == ["developer_marked:comment"]


def test_exactly_the_unmarked_routes_are_flagged():
    assert FLAGGED == {
        "/stock",                       # blank line between comment and route
        "/offers",                      # comment between decorator and function
        "/wishlist",                    # marked, but @login_required above the route decorator
        "/shop/<int:item_id>/reviews",  # "*" matches one part only
        "/News/archive",                # case matters
    }


def test_misplaced_login_decorator_still_wins_over_a_mark():
    finding = next(f for f in RESULT["findings"] if f["url_path"] == "/wishlist")
    assert "sits above the route decorator" in finding["explanation"]
    assert LABELS["/wishlist"] == []


def test_output_stays_valid_and_unconfirmed():
    assert RESULT["scan"]["files_skipped"] == []
    assert {f["finding_status"] for f in RESULT["findings"]} == {"unconfirmed"}
    assert schema_errors(RESULT, load_schema()) == []


# ---------------------------------------------------------------------------
# Small apps in a temporary folder
# ---------------------------------------------------------------------------

def write_app(folder, source, decisions=None):
    (folder / "app.py").write_text(textwrap.dedent(source))
    if decisions is not None:
        (folder / ".secureflow").mkdir()
        (folder / ".secureflow" / "route_decisions.json").write_text(decisions)


OPEN_APP = """
    from flask import Flask
    app = Flask(__name__)
    db = None

    @app.route("/catalog")
    def catalog():
        return str(db.execute("SELECT * FROM products").fetchall())
"""


def test_broken_json_is_ignored_and_reported(tmp_path):
    write_app(tmp_path, OPEN_APP, decisions='{ "public_routes": ["/catalog", }')
    result = run_engine(tmp_path)
    assert [f["url_path"] for f in result["findings"]] == ["/catalog"]  # still flagged
    skipped = result["scan"]["files_skipped"]
    assert len(skipped) == 1
    assert skipped[0]["file_path"] == ".secureflow/route_decisions.json"
    assert schema_errors(result, load_schema()) == []


def test_wrong_shape_is_ignored_as_a_whole(tmp_path):
    # One bad entry (no leading "/") makes the whole file count as broken,
    # so a typo never half-applies the developer's decisions.
    write_app(tmp_path, OPEN_APP, decisions=json.dumps({"public_routes": ["/catalog", "catalog"]}))
    result = run_engine(tmp_path)
    assert [f["url_path"] for f in result["findings"]] == ["/catalog"]
    assert "must be a list of paths" in result["scan"]["files_skipped"][0]["reason"]


def test_marked_routes_are_not_counted_as_protected_neighbours(tmp_path):
    # Group "api": 2 protected, 1 marked, 1 open. The marked route is left out,
    # so the open route has 2 of 2 protected neighbours (not 3 of 3).
    write_app(tmp_path, """
        from flask import Flask
        from flask_login import login_required
        app = Flask(__name__)
        db = None

        @app.route("/api/a")
        @login_required
        def a():
            return str(db.execute("SELECT 1").fetchall())

        @app.route("/api/b")
        @login_required
        def b():
            return str(db.execute("SELECT 1").fetchall())

        # secureflow: public
        @app.route("/api/status")
        def status():
            return str(db.execute("SELECT 1").fetchall())

        @app.route("/api/c")
        def c():
            return str(db.execute("SELECT 1").fetchall())
    """)
    result = run_engine(tmp_path)
    assert [f["url_path"] for f in result["findings"]] == ["/api/c"]
    assert "2 of 2 other routes in the same group are protected" in result["findings"][0]["explanation"]
