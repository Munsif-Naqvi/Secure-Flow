"""The missing-ownership-check (IDOR) rule (docs/03-detection-rules.md, part 10).

fixtures/idor_app has one route per case; the comment above each route says
whether it should be flagged and why.
"""

from schema_check import load_schema, schema_errors
from test_main import FIXTURES, run_engine

RESULT = run_engine(FIXTURES / "idor_app")
OWNERSHIP = {f["url_path"]: f for f in RESULT["findings"] if f["problem_type"] == "missing_ownership_check"}


def test_exactly_the_routes_without_an_ownership_check_are_flagged():
    assert sorted(OWNERSHIP) == [
        "/api/posts/rename",            # id from the JSON body, posts has a FOREIGN KEY to users
        "/invoices/view",               # table found in schema.sql (owner REFERENCES users)
        "/notes/<int:note_id>",         # URL variable
        "/notes/<int:note_id>/delete",  # DELETE by any id
        "/notes/raw",                   # `session.get(...) is None` is a login check, not ownership
        "/notes/view",                  # id from the query string
        "/orders/<order_id>",           # id inside an f-string query
        "/profile",                     # the session id is only the default
    ]


def test_ownership_checks_are_recognised():
    # if record owner != session user: turn away; query tied to the user; owner decorator.
    for path in ["/notes/checked", "/notes/<int:note_id>/edit", "/notes/mine/<int:note_id>",
                 "/orders/mine/<int:order_id>", "/notes/<int:note_id>/share"]:
        assert path not in OWNERSHIP, path


def test_queries_that_cannot_open_another_users_record_are_not_flagged():
    # shared table, unknown table, INSERT, and an id taken only from the session.
    for path in ["/products/<int:product_id>", "/gadgets/<int:gadget_id>", "/notes/new", "/me"]:
        assert path not in OWNERSHIP, path


def test_routes_without_a_login_check_are_left_to_the_missing_login_rule():
    open_route = [f for f in RESULT["findings"] if f["url_path"] == "/notes/open/<int:note_id>"]
    assert [f["problem_type"] for f in open_route] == ["missing_login"]


def test_explanation_and_fields():
    finding = OWNERSHIP["/notes/view"]
    assert finding["severity"] == "High"
    assert finding["problem_class"] == "access_control"
    assert finding["finding_status"] == "unconfirmed"
    assert finding["explanation"] == (
        "This route (GET /notes/view) checks that the visitor is logged in, but it reads a record from "
        "the notes table using a value the visitor chooses (id from the query string). In that table the "
        "user_id column says which user owns each row, and SecureFlow found no check that the record "
        "belongs to the visitor. A logged-in user may be able to see another user's data by changing that "
        "value. This was found by reading the code and has not been tested live."
    )
    delete = OWNERSHIP["/notes/<int:note_id>/delete"]["explanation"]
    assert "changes a record in the notes table" in delete
    assert "change or delete another user's data" in delete
    # The value that picks the record is named, not another visitor value in the query.
    assert "(id from the JSON body)" in OWNERSHIP["/api/posts/rename"]["explanation"]


def test_output_is_valid():
    assert schema_errors(RESULT, load_schema()) == []


def test_corpus_idor_route_is_found():
    from test_corpus import CORPUS
    findings = run_engine(CORPUS / "app_03_idor")["findings"]
    assert [(f["url_path"], f["problem_type"]) for f in findings] == [("/user/profile", "missing_ownership_check")]
    # app 5 has the same kind of route with an ownership check: not flagged.
    safe = run_engine(CORPUS / "app_05_safe_control")["findings"]
    assert safe == []
