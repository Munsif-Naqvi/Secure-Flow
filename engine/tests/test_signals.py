"""Stage 3 check: privileged words and neighbour consistency (docs/03-detection-rules.md, part 7).

fixtures/signals_app has one route per case; the comment above each route
gives the expected severity and why.
"""

from schema_check import load_schema, schema_errors
from test_main import FIXTURES, run_engine

RESULT = run_engine(FIXTURES / "signals_app")
FINDINGS = {f["url_path"]: f for f in RESULT["findings"]}

PRIVILEGED = "The name suggests this route handles sensitive data or actions."


def neighbour_sentence(n, m):
    return str(n) + " of " + str(m) + " other routes in the same group are protected, so this one may have been missed."


def test_severities():
    assert {path: f["severity"] for path, f in FINDINGS.items()} == {
        "/orders/<int:order_id>/invoice": "High",  # 3 protected neighbours in its Blueprint
        "/notes/recent": "Medium",                 # only 1 of 3 protected
        "/notes/popular": "Medium",
        "/help/search": "High",                    # path group "help", FAQ not counted
        "/team/calendar": "Medium",                # group of 2 is too small
        "/<int:id>/export": "High",                # "export" in the path
        "/<int:id>/view": "Medium",
        "/stats": "High",                          # "dump" in the handler name
        "/weather": "Medium",
    }


def test_blueprint_with_three_protected_routes_flags_the_fourth_as_high():
    finding = FINDINGS["/orders/<int:order_id>/invoice"]
    assert finding["severity"] == "High"
    assert neighbour_sentence(3, 3) in finding["explanation"]


def test_public_content_is_not_counted_as_a_neighbour():
    assert "/help/faq" not in FINDINGS
    assert neighbour_sentence(2, 2) in FINDINGS["/help/search"]["explanation"]


def test_groups_below_the_thresholds_add_nothing():
    for path in ["/notes/recent", "/notes/popular", "/team/calendar", "/weather", "/<int:id>/view"]:
        assert "other routes in the same group" not in FINDINGS[path]["explanation"], path
        assert PRIVILEGED not in FINDINGS[path]["explanation"], path


def test_privileged_word_in_path_or_handler_name_adds_one_sentence():
    assert PRIVILEGED in FINDINGS["/<int:id>/export"]["explanation"]
    assert PRIVILEGED in FINDINGS["/stats"]["explanation"]
    # The sentence goes before the last one, which always stays the same.
    assert FINDINGS["/stats"]["explanation"].endswith(PRIVILEGED + " This was found by reading the code and has not been tested live.")


def test_flask_path_syntax_is_kept_as_written():
    paths = [route["url_path"] for route in RESULT["routes"]]
    assert "/<int:id>/export" in paths
    assert "/orders/<int:order_id>/invoice" in paths


def test_findings_stay_unconfirmed_and_valid():
    assert {f["finding_status"] for f in RESULT["findings"]} == {"unconfirmed"}
    assert schema_errors(RESULT, load_schema()) == []
