"""Routes the developer marks as public (docs/03-detection-rules.md, part 8).

Some routes are public on purpose but the code rules cannot see it, for
example a product list that reads the database. The developer can say so in
one of two ways:

- a comment line `# secureflow: public` directly above the route's decorators;
- an entry in `<project>/.secureflow/route_decisions.json`:
      { "public_routes": ["/catalog", "/public/*"] }

A marked route is not flagged by the missing-login rule. It keeps a label in
`protections_found` so the decision stays visible. A mark is the developer's
own claim: the engine does not check it.
"""

import ast
import json
import os
import re

from secureflow.constants import MARKED_BY_COMMENT, MARKED_BY_DECISIONS_FILE
from secureflow.rules import is_public

# Where the decisions file lives, relative to the scanned project.
DECISIONS_FILE = ".secureflow/route_decisions.json"

# "# secureflow: public", in any case, with any spaces.
MARK_COMMENT = re.compile(r"^\s*#\s*secureflow\s*:\s*public\s*$", re.IGNORECASE)


def add_developer_marks(routes, project_path):
    """Label every route the developer marked as public.

    Returns entries for the `files_skipped` field (a broken decisions file).
    """
    patterns, skipped = read_decisions_file(project_path)
    source_lines = {}  # file_path -> list of lines, read once per file

    for route in routes:
        if not needs_decision(route):
            continue
        if route.file_path not in source_lines:
            source_lines[route.file_path] = read_lines(project_path, route.file_path)
        if has_mark_comment(route, source_lines[route.file_path]):
            route.protections_found = [MARKED_BY_COMMENT]
        elif any(path_matches(pattern, route.url_path) for pattern in patterns):
            route.protections_found = [MARKED_BY_DECISIONS_FILE]
    return skipped


def needs_decision(route):
    """True only for a route the missing-login rule would otherwise flag."""
    if route.protections_found:
        return False  # protected, or already labelled public content
    if route.misplaced_protections:
        # A @login_required above the route decorator shows the developer
        # wanted a login check. That contradicts a "public" mark, so the
        # route stays flagged and the explanation tells them to move it.
        return False
    return not is_public(route)  # allowlisted routes are not flagged anyway


# ---------------------------------------------------------------------------
# The comment
# ---------------------------------------------------------------------------

def read_lines(project_path, file_path):
    """The file's lines, or [] if it cannot be read. (Only read, never run.)"""
    try:
        with open(os.path.join(project_path, file_path), encoding="utf-8", errors="replace") as handle:
            return handle.read().splitlines()
    except OSError:
        return []


def first_line_of_route(route):
    """The line number the mark comment must sit right above.

    For a decorator route it is the topmost decorator of the function, so the
    comment can sit above a stack such as @app.route / @cache. For an
    add_url_rule route it is the add_url_rule line itself.
    """
    handler = route.handler
    if isinstance(handler, (ast.FunctionDef, ast.AsyncFunctionDef)) and handler.decorator_list:
        decorator_lines = [decorator.lineno for decorator in handler.decorator_list]
        if route.line_number in decorator_lines:
            return min(decorator_lines)
    return route.line_number


def has_mark_comment(route, lines):
    """True if one of the comment lines directly above the route is the mark.

    We walk upwards from the line above the route and stop at the first line
    that is not a comment (a blank line or code), so a mark further away
    does not count.
    """
    index = first_line_of_route(route) - 2  # line numbers start at 1, list indexes at 0
    while 0 <= index < len(lines) and lines[index].strip().startswith("#"):
        if MARK_COMMENT.match(lines[index]):
            return True
        index -= 1
    return False


# ---------------------------------------------------------------------------
# The decisions file
# ---------------------------------------------------------------------------

def read_decisions_file(project_path):
    """Return (patterns, skipped). A missing file is normal: no patterns.

    A broken file is ignored as a whole and reported in `skipped`, so one
    typo never half-applies the developer's decisions.
    """
    disk_path = os.path.join(project_path, DECISIONS_FILE)
    if not os.path.isfile(disk_path):
        return [], []
    try:
        with open(disk_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        return [], [skip_entry("could not read route decisions: " + str(error))]

    patterns = data.get("public_routes") if isinstance(data, dict) else None
    if not isinstance(patterns, list) or not all(isinstance(p, str) and p.startswith("/") for p in patterns):
        return [], [skip_entry('route decisions ignored: "public_routes" must be a list of paths starting with "/"')]
    return patterns, []


def skip_entry(reason):
    return {"file_path": DECISIONS_FILE, "reason": reason}


def path_matches(pattern, url_path):
    """True if the route's path matches the pattern.

    Both are split into parts at "/". They must have the same number of parts,
    and each part must be equal, or be "*" in the pattern (any one part).
    A trailing slash is ignored. Case matters, as it does in Flask.
    """
    pattern_parts = pattern.rstrip("/").split("/")
    path_parts = url_path.rstrip("/").split("/")
    if len(pattern_parts) != len(path_parts):
        return False
    return all(want == "*" or want == part for want, part in zip(pattern_parts, path_parts))
