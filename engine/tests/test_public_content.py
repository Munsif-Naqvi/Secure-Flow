"""Stage 2 check: the public content rule (docs/03-detection-rules.md, part 6).

fixtures/content_app has one route per case. The comment above each route says
whether it is public content or must still be flagged, and why.
"""

import sys
from pathlib import Path

from test_main import FIXTURES, run_engine

sys.path.insert(0, str(Path(__file__).parent.parent))  # so "secureflow" can be imported
from secureflow.protections import add_protections  # noqa: E402
from secureflow.public_content import not_public_content_reason  # noqa: E402
from secureflow.routes import collect_files, find_routes, parse_files  # noqa: E402

APP = FIXTURES / "content_app"
RESULT = run_engine(APP)
FLAGGED = {f["url_path"] for f in RESULT["findings"]}
PROTECTIONS = {r["url_path"]: r["protections_found"] for r in RESULT["routes"]}

PUBLIC_CONTENT = ["/news", "/robots.txt", "/hours", "/api/info", "/terms", "/faq", "/help"]


def reasons():
    """url_path -> why the rule said "not public content" (None if it is public content)."""
    trees, _ = parse_files(str(APP), ["app.py"])
    files = collect_files(trees)
    routes = find_routes(files)
    add_protections(routes, files)
    return {route.url_path: not_public_content_reason(route, files, str(APP)) for route in routes}


REASONS = reasons()


def test_public_content_routes_are_not_flagged_but_still_listed():
    for path in PUBLIC_CONTENT:
        assert path not in FLAGGED, path
        assert PROTECTIONS[path] == ["public_content:static_response"], path


def test_every_other_route_is_still_flagged():
    others = set(PROTECTIONS) - set(PUBLIC_CONTENT)
    assert len(others) == 21
    assert others <= FLAGGED


def test_each_flagged_route_is_stopped_by_the_right_check():
    assert REASONS["/search"] == "uses request, session, g, current_user, cookies or headers"
    assert REASONS["/greeting"] == "uses request, session, g, current_user, cookies or headers"
    assert REASONS["/whoami"] == "uses request, session, g, current_user, cookies or headers"
    assert REASONS["/theme"] == "uses request, session, g, current_user, cookies or headers"
    assert REASONS["/products"] == "uses the database, files, programs or the network"
    assert REASONS["/feedback"] == "accepts a method that is not GET, HEAD or OPTIONS"
    assert REASONS["/news/<int:news_id>"] == "path has a URL variable"
    assert REASONS["/version"] == "does not return a constant answer"
    assert REASONS["/club"] == "answer contains a sensitive word"
    assert REASONS["/admin/info"] == "path or handler name has a privileged word"
    assert REASONS["/report"] == "path or handler name has a privileged word"
    assert REASONS["/cached"] == "has a decorator that is not a route decorator"
    assert REASONS["/prices"] == "does not return a constant answer"
    assert REASONS["/motd"] == "body is more than a single return"
    assert REASONS["/welcome"] == "does not return a constant answer"
    assert REASONS["/api/stats"] == "does not return a constant answer"


def test_templates_must_exist_and_have_no_jinja_logic():
    template_problem = "template is missing or has Jinja expressions or statements"
    assert REASONS["/hello"] == template_problem    # {{ name }}
    assert REASONS["/menu"] == template_problem     # {% if %}
    assert REASONS["/child"] == template_problem    # extends a template with {{ title }}
    assert REASONS["/missing"] == template_problem  # no such file
    assert REASONS["/keys"] == "answer contains a sensitive word"  # "API_KEY" in the template


def test_public_content_findings_stay_unconfirmed_and_summary_counts_them():
    assert {f["finding_status"] for f in RESULT["findings"]} == {"unconfirmed"}
    assert RESULT["summary"]["suspects_found"] == len(RESULT["findings"]) == 21


def test_output_still_validates_against_the_schema():
    from schema_check import load_schema, schema_errors
    assert schema_errors(RESULT, load_schema()) == []
