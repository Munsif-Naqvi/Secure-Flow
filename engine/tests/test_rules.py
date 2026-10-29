"""Step 4 check: the missing-login rule and the shape of the findings.

The expected result for each route is also written in a comment above it in
the fixtures, so the two can be compared by eye.
"""

import hashlib

from schema_check import load_schema, schema_errors
from test_main import FIXTURES, run_engine

TINY = run_engine(FIXTURES / "tiny_app")
PUBLIC = run_engine(FIXTURES / "public_app")


def flagged(result):
    """[(file_path, line_number, url_path, severity)] for every finding."""
    return [(f["file_path"], f["line_number"], f["url_path"], f["severity"]) for f in result["findings"]]


def finding_for(result, url_path):
    matches = [f for f in result["findings"] if f["url_path"] == url_path]
    assert len(matches) == 1, url_path
    return matches[0]


# --- the Step 4 acceptance check --------------------------------------------

def test_output_validates_against_the_schema():
    schema = load_schema()
    for folder in ["tiny_app", "public_app", "hello_app", "locked_app", "partial_app", "session_app"]:
        assert schema_errors(run_engine(FIXTURES / folder), schema) == [], folder


def test_tiny_app_yields_exactly_the_expected_findings():
    assert flagged(TINY) == [
        # The account Blueprint: 12 of its 16 counted routes are protected, so its
        # 4 unprotected routes are High (neighbour consistency, part 7).
        ("account.py", 49, "/account/export", "High"),     # @login_required above the route; "export"
        ("account.py", 55, "/account/news", "High"),
        ("account.py", 86, "/account/me", "High"),           # session["user"] is only read
        ("account.py", 116, "/account/theme", "High"),
        ("admin.py", 38, "/reports/sales", "Medium"),     # its hook checks nothing
        ("app.py", 23, "/items", "High"),
        ("app.py", 29, "/status", "Medium"),
        ("app.py", 34, "/submit", "High"),
        ("app.py", 39, "/item/<int:item_id>", "High"),    # PUT
        ("app.py", 44, "/item/<int:item_id>", "High"),    # DELETE
        ("app.py", 49, "/item/<int:item_id>", "High"),    # PATCH
        ("app.py", 55, "/a", "Medium"),
        ("app.py", 56, "/b", "Medium"),
        ("app.py", 86, "/profile", "High"),               # MethodView with post()
        ("shop/api.py", 8, "/api/users", "High"),          # "users" is a privileged word
        ("shop/api.py", 14, "/api/users", "High"),
        ("shop/views.py", 6, "/shop/", "Medium"),         # "/shop" is not on the allowlist
        ("shop/views.py", 12, "/shop/orders/<int:order_id>", "High"),
        ("shop/views.py", 22, "/shop/cart", "High"),
    ]
    # Not flagged: "/", "/about" and "/contact" (public), and every protected route.


def test_every_finding_is_unconfirmed_and_counted_in_the_summary():
    assert {f["finding_status"] for f in TINY["findings"]} == {"unconfirmed"}
    assert TINY["summary"] == {"suspects_found": 19, "problems_confirmed": 0}


# --- public allowlist and severity ------------------------------------------

def test_public_app_findings():
    assert flagged(PUBLIC) == [
        ("app.py", 30, "/profile", "Medium"),
        ("app.py", 36, "/comments", "High"),
        ("app.py", 42, "/site-admin", "High"),
        ("app.py", 50, "/home", "Medium"),
        ("app.py", 58, "/reports", "Medium"),
    ]


def test_hello_app_home_page_is_public():
    assert run_engine(FIXTURES / "hello_app")["findings"] == []


# --- finding fields ---------------------------------------------------------

def test_finding_fields_and_explanation_template():
    finding = finding_for(PUBLIC, "/profile")
    expected_key = hashlib.sha1(b"/profile|missing_login|app.py").hexdigest()[:12]
    assert finding["finding_match_key"] == expected_key
    assert finding["problem_class"] == "access_control"
    assert finding["problem_type"] == "missing_login"
    assert finding["explanation"] == (
        "This route (GET /profile) has no login check that SecureFlow could find. "
        "Anyone who visits it may be able to use it without logging in. "
        "This was found by reading the code and has not been tested live."
    )


def test_explanation_names_a_login_decorator_above_the_route():
    explanation = finding_for(TINY, "/account/export")["explanation"]
    assert "A @login_required sits above the route decorator, so Flask ignores it; move it below." in explanation


def test_explanation_names_several_misplaced_decorators():
    explanation = finding_for(PUBLIC, "/reports")["explanation"]
    assert "@login_required, @roles_required('admin') sit above the route decorator" in explanation
