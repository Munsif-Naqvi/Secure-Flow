"""The missing-login rule (docs/03-detection-rules.md, part 3).

protections.py has already filled `protections_found` for every route. Here
we turn each route that has none into a finding, unless the route is on the
public allowlist (public_routes.py). Every finding is "unconfirmed": it comes
from reading the code only, nothing was tested live.
"""

import ast
import hashlib

from secureflow.public_routes import PUBLIC_FUNCTION_NAMES, PUBLIC_PATH_PREFIXES, PUBLIC_PATHS

# HTTP methods that change data. A route that accepts one of them is High severity.
CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def missing_login_findings(routes):
    """Return the list of missing_login findings, in the same order as `routes`."""
    findings = []
    for route in routes:
        if route.protections_found:
            continue  # protected
        # A login decorator above the route decorator shows the developer
        # wanted a login check, so the route is flagged even if it looks public.
        if is_public(route) and not route.misplaced_protections:
            continue
        findings.append(make_finding(route))
    return findings


def is_public(route):
    """True if the route's path or handler name is on the public allowlist."""
    path = route.url_path.lower()
    if any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
        return True
    # "/About/" and "/about" are the same page. Removing the slash from "/" leaves "", so keep "/".
    if (path.rstrip("/") or "/") in PUBLIC_PATHS:
        return True
    return handler_name(route.handler).lower() in PUBLIC_FUNCTION_NAMES


def handler_name(handler):
    """The function (or MethodView class) name, or "" if there is none."""
    if isinstance(handler, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return handler.name
    return ""


def severity(route):
    """High if the route can change data or is an admin page, otherwise Medium."""
    if CHANGING_METHODS.intersection(route.http_methods) or "admin" in route.url_path.lower():
        return "High"
    return "Medium"


def match_key(url_path, problem_type, file_path):
    """First 12 hex characters of SHA-1 of "<url_path>|<problem_type>|<file_path>".

    The same problem gets the same key in every scan, so later scans can be
    compared with earlier ones.
    """
    text = url_path + "|" + problem_type + "|" + file_path
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def explanation(route):
    """The plain-language explanation from the template in the detection rules."""
    methods = ", ".join(route.http_methods)
    parts = ["This route (" + methods + " " + route.url_path + ") has no login check that SecureFlow could find."]
    if route.misplaced_protections:
        names = ", ".join("@" + name for name in route.misplaced_protections)
        if len(route.misplaced_protections) == 1:
            parts.append("A " + names + " sits above the route decorator, so Flask ignores it; move it below.")
        else:
            parts.append(names + " sit above the route decorator, so Flask ignores them; move them below.")
    parts.append("Anyone who visits it may be able to use it without logging in.")
    parts.append("This was found by reading the code and has not been tested live.")
    return " ".join(parts)


def make_finding(route):
    """One finding in the format of docs/04-findings.schema.json."""
    return {
        "finding_match_key": match_key(route.url_path, "missing_login", route.file_path),
        "problem_class": "access_control",
        "problem_type": "missing_login",
        "severity": severity(route),
        "finding_status": "unconfirmed",  # the only status a code-only scan can give
        "url_path": route.url_path,
        "file_path": route.file_path,
        "line_number": route.line_number,
        "explanation": explanation(route),
    }
