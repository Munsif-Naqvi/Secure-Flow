"""Class-based routes: `@blp.route` on a MethodView class (Flask-Smorest style).

Each method of the class (get, put, delete, ...) is its own route with its own
protections. The expected results are also written in comments in
fixtures/class_view_app/resources.py, so the two can be compared by eye.
"""

from schema_check import load_schema, schema_errors
from test_main import FIXTURES, run_engine

RESULT = run_engine(FIXTURES / "class_view_app")


def route_tuples():
    return [(r["line_number"], r["http_methods"], r["url_path"], r["protections_found"])
            for r in RESULT["routes"]]


def test_each_method_of_a_class_is_its_own_route():
    # Line = the method's topmost decorator, or its `def` line.
    # `helper` is not an HTTP method name, so it is not a route.
    assert route_tuples() == [
        (15, ["GET"], "/item/<string:item_id>", ["jwt_required"]),
        (20, ["DELETE"], "/item/<string:item_id>", []),
        (25, ["PUT"], "/item/<string:item_id>", ["jwt_required"]),
        (40, ["GET"], "/store", ["jwt_required"]),     # from the class `decorators` list
        (43, ["POST"], "/store", ["jwt_required"]),    # from the class `decorators` list
        (52, ["GET"], "/admin/stats", []),             # decorator on the class protects nothing
    ]


def test_only_the_unprotected_methods_are_flagged():
    flagged = [(f["line_number"], f["problem_type"], f["url_path"]) for f in RESULT["findings"]]
    assert flagged == [
        (20, "missing_login", "/item/<string:item_id>"),
        (52, "missing_login", "/admin/stats"),
    ]


def test_class_name_is_read_for_privileged_words():
    # The method is only called "get"; "admin" comes from the path and the class
    # name AdminStats. Either way the finding is High.
    admin = [f for f in RESULT["findings"] if f["url_path"] == "/admin/stats"][0]
    assert admin["severity"] == "High"


def test_decorator_on_the_class_is_not_reported_as_misplaced():
    # "Move it below the route decorator" would be wrong advice for a class,
    # so the explanation does not say it.
    admin = [f for f in RESULT["findings"] if f["url_path"] == "/admin/stats"][0]
    assert "above the route decorator" not in admin["explanation"]


def test_output_matches_the_schema():
    assert schema_errors(RESULT, load_schema()) == []
