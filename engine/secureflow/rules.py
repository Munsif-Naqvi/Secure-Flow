"""The missing-login rule (docs/03-detection-rules.md, part 3).

protections.py has already filled `protections_found` for every route. Here
we turn each route that has none into a finding, unless the route is on the
public allowlist (public_routes.py) or was labelled public content
(public_content.py). Every finding is "unconfirmed": it comes from reading the
code only, nothing was tested live.

Two signals can raise a finding to High (part 7 of the rules):
- privileged words: the path or handler name suggests sensitive data or actions;
- neighbour consistency: most other routes in the same group are protected.
"""

import ast
import hashlib

from secureflow.constants import NEIGHBOUR_MIN_ROUTES, NEIGHBOUR_PROTECTED_SHARE, PRIVILEGED_WORDS, PUBLIC_CONTENT_LABEL
from secureflow.public_routes import PUBLIC_FUNCTION_NAMES, PUBLIC_PATH_PREFIXES, PUBLIC_PATHS

# HTTP methods that change data. A route that accepts one of them is High severity.
CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def missing_login_findings(routes):
    """Return the list of missing_login findings, in the same order as `routes`."""
    neighbours = neighbour_counts(routes)
    findings = []
    for route in routes:
        if is_flag_candidate(route):
            findings.append(make_finding(route, neighbours))
    return findings


def is_flag_candidate(route):
    """True if the missing-login rule flags this route."""
    if route.protections_found:
        return False  # protected, or labelled public content
    # A login decorator above the route decorator shows the developer
    # wanted a login check, so the route is flagged even if it looks public.
    if is_public(route) and not route.misplaced_protections:
        return False
    return True


def is_public_content(route):
    return PUBLIC_CONTENT_LABEL in route.protections_found


def has_privileged_word(text):
    """True if the text (a path or a function name) contains a privileged word, in any case."""
    text = text.lower()
    return any(word in text for word in PRIVILEGED_WORDS)


def is_privileged(route):
    return has_privileged_word(route.url_path) or has_privileged_word(handler_name(route.handler))


# ---------------------------------------------------------------------------
# Neighbour consistency
# ---------------------------------------------------------------------------

def group_of(route):
    """The group a route belongs to: its Blueprint, or else the first part of its path.

    "/orders/<int:id>/export" on the app -> ("path", "orders").
    """
    if route.owner is not None and route.owner.kind == "blueprint":
        return ("blueprint", route.owner.file_path, route.owner.name)
    first_part = route.url_path.strip("/").split("/")[0]
    return ("path", first_part)


def neighbour_counts(routes):
    """For each group: (routes counted, routes protected).

    Only routes that need a login decision are counted: routes on the public
    allowlist and routes labelled public content are left out, because being
    open is expected for them.
    """
    counts = {}
    for route in routes:
        if is_public_content(route) or not (route.protections_found or is_flag_candidate(route)):
            continue
        counted, protected = counts.get(group_of(route), (0, 0))
        counts[group_of(route)] = (counted + 1, protected + (1 if route.protections_found else 0))
    return counts


def protected_neighbours(route, neighbours):
    """(N, M) when N of the M other routes in the route's group are protected and
    the group passes the thresholds, else None."""
    counted, protected = neighbours.get(group_of(route), (0, 0))
    if counted < NEIGHBOUR_MIN_ROUTES or protected / counted < NEIGHBOUR_PROTECTED_SHARE:
        return None
    # This route is unprotected, so all N protected routes are "other" routes.
    return protected, counted - 1


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


def severity(route, neighbours):
    """High if the route can change data, has a privileged word in its path or
    handler name, or most of its neighbours are protected. Otherwise Medium."""
    if CHANGING_METHODS.intersection(route.http_methods) or is_privileged(route):
        return "High"
    if protected_neighbours(route, neighbours):
        return "High"
    return "Medium"


def match_key(url_path, problem_type, file_path):
    """First 12 hex characters of SHA-1 of "<url_path>|<problem_type>|<file_path>".

    The same problem gets the same key in every scan, so later scans can be
    compared with earlier ones.
    """
    text = url_path + "|" + problem_type + "|" + file_path
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def explanation(route, neighbours):
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
    if is_privileged(route):
        parts.append("The name suggests this route handles sensitive data or actions.")
    others = protected_neighbours(route, neighbours)
    if others:
        parts.append(str(others[0]) + " of " + str(others[1])
                     + " other routes in the same group are protected, so this one may have been missed.")
    parts.append("This was found by reading the code and has not been tested live.")
    return " ".join(parts)


def make_finding(route, neighbours):
    """One finding in the format of docs/04-findings.schema.json."""
    return {
        "finding_match_key": match_key(route.url_path, "missing_login", route.file_path),
        "problem_class": "access_control",
        "problem_type": "missing_login",
        "severity": severity(route, neighbours),
        "finding_status": "unconfirmed",  # the only status a code-only scan can give
        "url_path": route.url_path,
        "file_path": route.file_path,
        "line_number": route.line_number,
        "explanation": explanation(route, neighbours),
    }
