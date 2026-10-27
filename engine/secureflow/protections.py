"""Finding the login protections of each route (docs/03-detection-rules.md, part 2).

For every route found by routes.py we look for four kinds of protection and
write what we found into `route.protections_found`:

a. A login-style decorator on the handler, e.g. `@login_required`.
b. A `@bp.before_request` (or `@app.before_request`) hook that contains a check.
c. A `decorators = [login_required]` list on a MethodView class.
d. A simple check written inside the handler, e.g. `if not current_user.is_authenticated`.

Like routes.py, this only reads the ast tree. The scanned code is never run.
This file only *records* protections. Deciding which routes are a problem
(the missing-login rule) is done in rules.py.
"""

import ast

from secureflow.routes import last_name, lookup_object, static_text

# (a) Decorator names that mean "login or role required". Compared in lower case.
KNOWN_DECORATORS = {
    "login_required", "jwt_required", "fresh_jwt_required", "token_required",
    "auth_required", "admin_required", "roles_required", "role_required",
    "permission_required", "requires_auth", "verify_jwt_in_request",
}
# `login_manager.login_required` from the rules is covered too: we compare
# only the last part of a dotted name, which is "login_required".

# (a) A decorator whose name contains one of these is probably a home-made
# protection. It is recorded as "custom_decorator:<name>" so it is clear it is a guess.
CUSTOM_DECORATOR_WORDS = ["login", "auth", "admin", "role", "permission", "jwt"]

# (d) A session key containing one of these words is taken to mean "the logged-in user".
SESSION_USER_WORDS = ["user", "uid", "login", "auth", "token"]

# (b) A hook that reads one of these on `request` usually skips some pages
# (for example "if request.endpoint == 'login': return"), so it may not cover every route.
REQUEST_ROUTE_ATTRIBUTES = {"endpoint", "path", "url_rule", "blueprint"}


def add_protections(routes, files):
    """Fill `protections_found` for every route. `files` comes from routes.collect_files."""
    hooks = find_before_request_hooks(files)
    for route in routes:
        found = []
        found += decorator_protections(route.decorators)
        found += class_protections(route.handler)
        found += hook_protections(route, hooks)
        found += inline_checks(route.handler)
        # Keep each label once, in the order it was found.
        route.protections_found = list(dict.fromkeys(found))
        route.misplaced_protections = misplaced_protections(route.decorators_above)


def misplaced_protections(decorators_above):
    """Login-style decorators written above `@x.route`, as they appear in the code.

    Flask ignores these (it saved the view before they wrapped it), so they are
    not protections. We keep their text, e.g. "login_required" or
    "auth.login_required", so the finding can tell the developer to move them.
    """
    names = []
    for decorator in decorators_above:
        if protection_label(decorator):
            # ast.unparse turns the node back into code text, e.g. "jwt_required()".
            names.append(ast.unparse(decorator))
    return names


# ---------------------------------------------------------------------------
# (a) Decorators and (c) MethodView decorators lists
# ---------------------------------------------------------------------------

def decorator_protections(decorators):
    labels = []
    for decorator in decorators:
        label = protection_label(decorator)
        if label:
            labels.append(label)
    return labels


def protection_label(node):
    """The label for one decorator (or one item of a `decorators` list), or None.

    Works for `@login_required`, `@auth.login_required` and called forms such
    as `@jwt_required()` or `@roles_required("admin")`.
    """
    if isinstance(node, ast.Call):
        node = node.func  # @jwt_required() -> look at jwt_required
    name = last_name(node)
    if not name:
        return None
    if name.lower() in KNOWN_DECORATORS:
        return name.lower()
    if any(word in name.lower() for word in CUSTOM_DECORATOR_WORDS):
        return "custom_decorator:" + name
    return None


def class_protections(handler):
    """(c) `decorators = [login_required, ...]` inside a MethodView class."""
    if not isinstance(handler, ast.ClassDef):
        return []
    labels = []
    for statement in handler.body:
        if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id == "decorators"
                and isinstance(statement.value, (ast.List, ast.Tuple))):
            labels += decorator_protections(statement.value.elts)
    return labels


# ---------------------------------------------------------------------------
# (b) before_request hooks
# ---------------------------------------------------------------------------

def find_before_request_hooks(files):
    """Find functions decorated with `@x.before_request` that contain a check.

    Returns a dict: FlaskObject (app or Blueprint) -> label, where the label is
    "before_request", or "before_request_partial" when the hook seems to skip
    some pages. A hook without any check (for example one that only logs) is
    not a protection and is left out.
    """
    hooks = {}
    for info in files.values():
        for node in ast.walk(info.tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not (isinstance(decorator, ast.Attribute) and decorator.attr == "before_request"
                        and isinstance(decorator.value, ast.Name)):
                    continue
                owner = lookup_object(decorator.value.id, info, files)
                if owner is None or not inline_checks(node):
                    continue
                label = "before_request_partial" if reads_request_route(node) else "before_request"
                # Two hooks on one object: a full one wins over a partial one.
                if hooks.get(owner) != "before_request":
                    hooks[owner] = label
    return hooks


def hook_protections(route, hooks):
    """The hook labels that cover this route.

    A Blueprint's hook covers that Blueprint's routes. An app's hook runs for
    every request, so it covers the app's routes and every Blueprint's routes.
    (We assume the project has one Flask app, which is the usual case.)
    """
    labels = []
    if route.owner in hooks:
        labels.append(hooks[route.owner])
    for owner, label in hooks.items():
        if owner.kind == "app" and owner is not route.owner and route.owner.kind == "blueprint":
            labels.append(label)
    return labels


def reads_request_route(function):
    """True if the function reads request.endpoint, request.path and the like."""
    for node in ast.walk(function):
        if (isinstance(node, ast.Attribute) and node.attr in REQUEST_ROUTE_ATTRIBUTES
                and last_name(node.value) == "request"):
            return True
    return False


# ---------------------------------------------------------------------------
# (d) Simple checks written inside a function body
# ---------------------------------------------------------------------------

def inline_checks(function):
    """Labels for the login checks found inside a handler or hook body.

    `function` can also be a MethodView class or None; then nothing is found,
    because the rules only list checks in a handler or hook body.
    """
    if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    labels = []
    header_names = names_assigned_from_authorization_header(function)
    for statement in function.body:
        for node in ast.walk(statement):
            labels += checks_in_node(node, header_names)
    return labels


def checks_in_node(node, header_names):
    labels = []

    # current_user.is_authenticated / current_user.is_active
    if (isinstance(node, ast.Attribute) and node.attr in ("is_authenticated", "is_active")
            and last_name(node.value) == "current_user"):
        labels.append("inline:current_user." + node.attr)

    # session.get("user_id"), session["user"], "user_id" in session
    key = session_key(node)
    if key is not None and any(word in key.lower() for word in SESSION_USER_WORDS):
        labels.append("inline:session_user_check")

    if isinstance(node, ast.Call):
        called = last_name(node.func)
        # abort(401) / abort(403): "not logged in" / "not allowed"
        if called == "abort" and node.args and isinstance(node.args[0], ast.Constant) \
                and node.args[0].value in (401, 403):
            labels.append("inline:abort_" + str(node.args[0].value))
        # Flask-JWT-Extended checks
        if called in ("get_jwt_identity", "verify_jwt_in_request"):
            labels.append("inline:" + called)

    if isinstance(node, ast.If):
        # if <test of session or current_user>: ... redirect(<something with "login">)
        if mentions_session_or_user(node.test) and any(is_login_redirect(n) for n in walk_list(node.body)):
            labels.append("inline:login_redirect")
        # if request.headers.get("Authorization") ...  (directly, or through a variable)
        if any(is_authorization_header(n) or (isinstance(n, ast.Name) and n.id in header_names)
               for n in ast.walk(node.test)):
            labels.append("inline:authorization_header")
    return labels


def session_key(node):
    """The key text if `node` reads the session with a plain-text key, else None."""
    # session.get("key")
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get" and last_name(node.func.value) == "session" and node.args):
        return static_text(node.args[0], {})
    # session["key"]
    if isinstance(node, ast.Subscript) and last_name(node.value) == "session":
        return static_text(node.slice, {})
    # "key" in session / "key" not in session
    if (isinstance(node, ast.Compare) and len(node.ops) == 1
            and isinstance(node.ops[0], (ast.In, ast.NotIn))
            and last_name(node.comparators[0]) == "session"):
        return static_text(node.left, {})
    return None


def mentions_session_or_user(test):
    return any(isinstance(n, ast.Name) and n.id in ("session", "current_user") for n in ast.walk(test))


def is_login_redirect(node):
    """`redirect(...)` whose arguments contain text with "login", e.g. redirect(url_for("login"))."""
    if not (isinstance(node, ast.Call) and last_name(node.func) == "redirect"):
        return False
    for argument in node.args:
        for part in ast.walk(argument):
            if isinstance(part, ast.Constant) and isinstance(part.value, str) and "login" in part.value.lower():
                return True
    return False


def is_authorization_header(node):
    """`request.headers.get("Authorization")` (the header name in any case)."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"):
        return False
    headers = node.func.value
    if not (isinstance(headers, ast.Attribute) and headers.attr == "headers"
            and last_name(headers.value) == "request"):
        return False
    text = static_text(node.args[0], {}) if node.args else None
    return text is not None and text.lower() == "authorization"


def names_assigned_from_authorization_header(function):
    """Variables set like `token = request.headers.get("Authorization")` in this function."""
    names = set()
    for node in ast.walk(function):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and is_authorization_header(node.value)):
            names.add(node.targets[0].id)
    return names


def walk_list(statements):
    """ast.walk over a list of statements (such as the body of an `if`)."""
    for statement in statements:
        yield from ast.walk(statement)
