"""Step 3 check: each route shows the login protections the engine found.

The expected protections are also written in a comment above each route in
the fixtures, so the two can be compared by eye. An empty list means the
engine found no protection (Step 4 will turn those into findings).
"""

from test_main import FIXTURES, run_engine


def protections_by_route(folder):
    """{(file_path, url_path): protections_found} for every route of a fixture app."""
    return {(r["file_path"], r["url_path"]): r["protections_found"] for r in run_engine(folder)["routes"]}


TINY = protections_by_route(FIXTURES / "tiny_app")


def account(path):
    return TINY[("account.py", "/account" + path)]


# --- (a) decorators -------------------------------------------------------

def test_login_required_decorator_below_the_route():
    assert account("/settings") == ["login_required"]


def test_called_decorator_like_jwt_required_with_brackets():
    assert account("/token") == ["jwt_required"]


def test_dotted_decorator_name_uses_its_last_part():
    assert account("/billing") == ["login_required"]


def test_role_decorator_and_a_guessed_custom_decorator_in_order():
    assert account("/staff") == ["roles_required", "custom_decorator:check_admin_rights"]


def test_login_decorator_above_the_route_decorator_does_not_count():
    # Flask saved the view before @login_required wrapped it, so the route is open.
    assert account("/export") == []


def test_unrelated_decorator_is_not_a_protection():
    assert account("/news") == []


def test_add_url_rule_counts_all_decorators_of_the_function():
    assert account("/avatar") == ["login_required"]


# --- (c) MethodView decorators list -----------------------------------------

def test_method_view_decorators_list():
    assert account("/addresses") == ["login_required"]


# --- (d) inline checks ------------------------------------------------------

def test_current_user_check_and_abort_401():
    assert account("/orders") == ["inline:current_user.is_authenticated", "inline:abort_401"]


def test_user_id_not_in_session_with_redirect_to_login():
    assert account("/cart") == ["inline:login_redirect", "inline:session_user_check"]


def test_redirect_to_login_inside_a_session_if():
    assert account("/wishlist") == ["inline:login_redirect"]


def test_session_user_key_read_directly():
    assert account("/me") == ["inline:session_user_check"]


def test_abort_403():
    assert account("/close") == ["inline:abort_403"]


def test_authorization_header_tested_through_a_variable():
    assert account("/api-key") == ["inline:authorization_header"]


def test_get_jwt_identity():
    assert account("/whoami") == ["inline:get_jwt_identity"]


def test_abort_404_and_non_user_session_key_are_not_protections():
    assert account("/theme") == []


# --- (b) before_request hooks -----------------------------------------------

def test_blueprint_hook_with_a_check_protects_its_routes():
    assert TINY[("admin.py", "/admin/users")] == ["before_request"]
    assert TINY[("admin.py", "/admin/users/<int:user_id>/delete")] == ["before_request"]


def test_blueprint_hook_without_a_check_protects_nothing():
    assert TINY[("admin.py", "/reports/sales")] == []


def test_app_hook_protects_app_and_blueprint_routes():
    locked = protections_by_route(FIXTURES / "locked_app")
    assert locked == {
        ("app.py", "/dashboard"): ["before_request"],
        ("app.py", "/api/data"): ["before_request"],
    }


def test_app_hook_that_skips_some_endpoints_is_partial():
    partial = protections_by_route(FIXTURES / "partial_app")
    assert partial == {
        ("app.py", "/login"): ["before_request_partial"],
        ("app.py", "/notes"): ["before_request_partial"],
    }


# --- the Step 3 acceptance check --------------------------------------------

def test_tiny_app_unprotected_routes_show_no_protection():
    # The Step 2 routes in app.py and shop/ have no login check at all.
    for (file_path, url_path), protections in TINY.items():
        if file_path == "app.py" or file_path.startswith("shop/"):
            assert protections == [], url_path


def test_hello_app_route_has_no_protection():
    assert protections_by_route(FIXTURES / "hello_app") == {("app.py", "/"): []}
