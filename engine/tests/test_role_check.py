"""The missing-role-check rule (docs/03-detection-rules.md, part 9).

fixtures/role_app has one route per case; the comment above each route says
whether it should be flagged and why.
"""

from schema_check import load_schema, schema_errors
from test_main import FIXTURES, run_engine

RESULT = run_engine(FIXTURES / "role_app")
ROLE = {f["url_path"]: f for f in RESULT["findings"] if f["problem_type"] == "missing_role_check"}


def test_exactly_the_admin_routes_without_a_role_check_are_flagged():
    assert sorted(ROLE) == [
        "/admin/purge",     # @admin_only above the route decorator: Flask ignores it
        "/admin/settings",  # admin path, login only
        "/admin/stats",     # the role is read but never used to turn anyone away
        "/panel",           # "admin" in the handler name
        "/tools/cleanup",   # "admin" in the Blueprint's variable name
    ]


def test_role_checks_that_turn_the_visitor_away_are_recognised():
    # abort(403), return ..., 403, redirect, a home-made @admin_only,
    # @roles_required("admin") and a Blueprint's before_request role hook.
    for path in ["/admin/users", "/admin/logs", "/admin/backup", "/admin/reports", "/admin/roles", "/staff/admin/rota"]:
        assert path not in ROLE, path


def test_routes_without_a_login_check_are_left_to_the_missing_login_rule():
    # One finding per route: an open admin route is "missing_login", not both.
    open_route = [f for f in RESULT["findings"] if f["url_path"] == "/admin/open"]
    assert [f["problem_type"] for f in open_route] == ["missing_login"]


def test_logged_in_routes_without_an_admin_name_are_not_flagged():
    assert "/dashboard" not in ROLE


def test_explanation_and_fields():
    finding = ROLE["/admin/settings"]
    assert finding["severity"] == "High"
    assert finding["problem_class"] == "access_control"
    assert finding["finding_status"] == "unconfirmed"
    assert finding["explanation"] == (
        "This route (GET /admin/settings) checks that the visitor is logged in, but SecureFlow found "
        "no admin or role check. Its name suggests it is meant for admins, so any logged-in user may "
        "be able to use it. This was found by reading the code and has not been tested live."
    )
    assert "A @admin_only sits above the route decorator" in ROLE["/admin/purge"]["explanation"]


def test_findings_stay_in_code_order_and_valid():
    lines = [(f["file_path"], f["line_number"]) for f in RESULT["findings"]]
    assert lines == sorted(lines)
    assert schema_errors(RESULT, load_schema()) == []


def test_tiny_app_admin_blueprint_hook_checks_login_only():
    # tiny_app's admin_bp hook checks current_user.is_authenticated, not a role.
    tiny = run_engine(FIXTURES / "tiny_app")
    role_paths = [f["url_path"] for f in tiny["findings"] if f["problem_type"] == "missing_role_check"]
    assert role_paths == ["/admin/users", "/admin/users/<int:user_id>/delete"]
