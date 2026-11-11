"""The missing-role-check rule (docs/03-detection-rules.md, part 9).

A route for admins needs two checks: "is the visitor logged in?" and "is the
visitor an admin?". The missing-login rule (rules.py) covers the first. This
rule looks at routes that DO have a login check and whose name says they are
for admins, and flags the ones where SecureFlow finds no role check. Then any
logged-in user, not only admins, may be able to use the route.

A role check is one of:
- a role-style decorator below the route decorator, e.g. @admin_required,
  @roles_required("admin"), or a home-made one whose name contains "admin" or
  "role";
- an `if` in the handler that tests a role and turns the visitor away, e.g.
      if session.get("role") != "admin":
          abort(403)
- the same kind of `if` in a before_request hook of the route's Blueprint or app.

Like the other rules, this only reads the code. Every finding is "unconfirmed".
"""

import ast

from secureflow.constants import ADMIN_ROUTE_WORDS, PUBLIC_LABELS, ROLE_WORDS
from secureflow.protections import protection_label, turns_visitor_away, walk_list
from secureflow.routes import lookup_object
from secureflow.rules import match_key, route_name

# Decorator labels from protections.py that already check a role, not only a login.
ROLE_DECORATOR_LABELS = {"admin_required", "roles_required", "role_required", "permission_required"}


def missing_role_findings(routes, files):
    """Return the missing_role_check findings, in the same order as `routes`."""
    role_hooks = find_role_hooks(files)
    findings = []
    for route in routes:
        if is_login_protected(route) and is_admin_style(route) and not has_role_check(route, role_hooks):
            findings.append(make_finding(route))
    return findings


def is_login_protected(route):
    """True if the route has a real protection (not just a "public on purpose" label).

    Routes without any protection are already flagged by the missing-login
    rule, so they are not flagged a second time here.
    """
    real = [label for label in route.protections_found if label not in PUBLIC_LABELS]
    return bool(real)


def contains_admin_word(text):
    text = text.lower()
    return any(word in text for word in ADMIN_ROUTE_WORDS)


def is_admin_style(route):
    """True if the path, the handler name or the Blueprint's variable name says "admin"."""
    names = [route.url_path, route_name(route)]
    if route.owner is not None and route.owner.kind == "blueprint":
        names.append(route.owner.name)
    return any(contains_admin_word(name) for name in names)


# ---------------------------------------------------------------------------
# Finding a role check
# ---------------------------------------------------------------------------

def has_role_check(route, role_hooks):
    return (role_decorator(route) or role_check_in(route.handler)
            or route.owner in role_hooks or any(owner.kind == "app" for owner in role_hooks))


def role_decorator(route):
    """True if a decorator that wraps the view (or a MethodView `decorators` list) checks a role."""
    decorators = list(route.decorators)
    if isinstance(route.handler, ast.ClassDef):
        for statement in route.handler.body:
            if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == "decorators"
                    and isinstance(statement.value, (ast.List, ast.Tuple))):
                decorators += statement.value.elts
    for decorator in decorators:
        label = protection_label(decorator)
        if label in ROLE_DECORATOR_LABELS:
            return True
        if label and label.startswith("custom_decorator:") and contains_role_word(label):
            return True
    return False


def role_check_in(function):
    """True if the function body has `if <role test>: <turn the visitor away>`.

    Only a check that can stop the visitor counts. Just reading the role, as
    in `role = session.get("role")`, protects nothing.
    """
    if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for node in walk_list(function.body):
        if isinstance(node, ast.If) and tests_role(node.test):
            if turns_visitor_away(node.body) or turns_visitor_away(node.orelse):
                return True
    return False


def tests_role(test):
    """True if an `if` test mentions a role: a name, attribute or text such as
    `role`, `is_admin`, `has_role(...)` or "admin"."""
    for node in ast.walk(test):
        if isinstance(node, ast.Name) and contains_role_word(node.id):
            return True
        if isinstance(node, ast.Attribute) and contains_role_word(node.attr):
            return True
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and contains_role_word(node.value):
            return True
    return False


def contains_role_word(text):
    text = text.lower()
    return any(word in text for word in ROLE_WORDS)


def find_role_hooks(files):
    """The apps and Blueprints whose @x.before_request hook contains a role check."""
    owners = set()
    for info in files.values():
        for node in ast.walk(info.tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if (isinstance(decorator, ast.Attribute) and decorator.attr == "before_request"
                        and isinstance(decorator.value, ast.Name) and role_check_in(node)):
                    owner = lookup_object(decorator.value.id, info, files)
                    if owner is not None:
                        owners.add(owner)
    return owners


# ---------------------------------------------------------------------------
# The finding
# ---------------------------------------------------------------------------

def explanation(route):
    methods = ", ".join(route.http_methods)
    parts = ["This route (" + methods + " " + route.url_path + ") checks that the visitor is logged in, "
             "but SecureFlow found no admin or role check."]
    # A role decorator above the route decorator is ignored by Flask (rules part 2).
    misplaced = [name for name in route.misplaced_protections if contains_role_word(name)]
    if len(misplaced) == 1:
        parts.append("A @" + misplaced[0] + " sits above the route decorator, so Flask ignores it; move it below.")
    elif misplaced:
        parts.append(", ".join("@" + name for name in misplaced)
                     + " sit above the route decorator, so Flask ignores them; move them below.")
    parts.append("Its name suggests it is meant for admins, so any logged-in user may be able to use it.")
    parts.append("This was found by reading the code and has not been tested live.")
    return " ".join(parts)


def make_finding(route):
    """One finding in the format of docs/04-findings.schema.json."""
    return {
        "finding_match_key": match_key(route.url_path, "missing_role_check", route.file_path),
        "problem_class": "access_control",
        "problem_type": "missing_role_check",
        "severity": "High",  # an admin route open to every logged-in user
        "finding_status": "unconfirmed",
        "url_path": route.url_path,
        "file_path": route.file_path,
        "line_number": route.line_number,
        "explanation": explanation(route),
    }
