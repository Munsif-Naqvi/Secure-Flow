"""Step 2 check: the route finder lists every route of tiny_app correctly.

Each expected route below is also described in a comment above the route in
fixtures/tiny_app, so the two can be compared by eye.
"""

import json

from test_main import FIXTURES, run_engine

# (file_path, line_number, http_methods, url_path), in the order the engine prints them.
TINY_APP_ROUTES = [
    ("app.py", 17, ["GET"], "/"),
    ("app.py", 23, ["GET", "POST"], "/items"),
    ("app.py", 29, ["GET"], "/status"),
    ("app.py", 34, ["POST"], "/submit"),
    ("app.py", 39, ["PUT"], "/item/<int:item_id>"),
    ("app.py", 44, ["DELETE"], "/item/<int:item_id>"),
    ("app.py", 49, ["PATCH"], "/item/<int:item_id>"),
    ("app.py", 55, ["GET"], "/a"),
    ("app.py", 56, ["GET"], "/b"),
    ("app.py", 66, ["GET"], "/about"),
    ("app.py", 74, ["GET", "POST"], "/contact"),
    ("app.py", 86, ["GET", "POST"], "/profile"),
    ("shop/api.py", 8, ["GET"], "/api/users"),
    ("shop/api.py", 14, ["POST"], "/api/users"),
    ("shop/views.py", 6, ["GET"], "/shop/"),
    ("shop/views.py", 12, ["GET", "DELETE"], "/shop/orders/<int:order_id>"),
    ("shop/views.py", 22, ["POST"], "/shop/cart"),
]

ROUTE_KEYS = {"url_path", "http_methods", "file_path", "line_number", "protections_found"}


def as_tuples(routes):
    return [(r["file_path"], r["line_number"], r["http_methods"], r["url_path"]) for r in routes]


def test_tiny_app_routes_are_all_found_with_paths_methods_files_and_lines():
    result = run_engine(FIXTURES / "tiny_app")
    assert as_tuples(result["routes"]) == TINY_APP_ROUTES


def test_routes_have_exactly_the_schema_fields_and_no_protections_yet():
    # The fields come from docs/04-findings.schema.json ("routes" items).
    # Protection detection is Step 3, so protections_found is always empty now.
    schema = json.loads((FIXTURES.parent.parent.parent / "docs" / "04-findings.schema.json").read_text())
    assert set(schema["properties"]["routes"]["items"]["required"]) == ROUTE_KEYS
    for route in run_engine(FIXTURES / "tiny_app")["routes"]:
        assert set(route) == ROUTE_KEYS
        assert isinstance(route["url_path"], str)
        assert all(isinstance(m, str) for m in route["http_methods"])
        assert isinstance(route["line_number"], int) and route["line_number"] >= 1
        assert route["protections_found"] == []


def test_file_with_syntax_error_is_skipped_not_crashed():
    scan = run_engine(FIXTURES / "tiny_app")["scan"]
    assert scan["files_skipped"] == [{"file_path": "broken.py", "reason": "syntax error on line 2"}]
    assert scan["files_scanned"] == 4  # app.py, shop/__init__.py, shop/views.py, shop/api.py


def test_hello_app_has_its_one_route():
    result = run_engine(FIXTURES / "hello_app")
    assert as_tuples(result["routes"]) == [("app.py", 7, ["GET"], "/")]


def test_folder_without_python_files_gives_valid_json_with_no_routes(tmp_path):
    (tmp_path / "notes.txt").write_text("not python")
    result = run_engine(tmp_path)
    assert result["routes"] == []
    assert result["findings"] == []
    assert result["scan"]["files_scanned"] == 0
