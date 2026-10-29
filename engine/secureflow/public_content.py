"""The public content rule (docs/03-detection-rules.md, part 6).

Some routes have no login check because they do not need one: they always
return the same harmless text, whoever asks. This file recognises such routes
by reading what the handler *does*, not what the route is called.

The rule is strict on purpose. A route counts as public content only when
every check below passes. If any check fails, or we cannot tell, the route is
treated as usual and the missing-login rule can still flag it. A response that
is the same for everyone does not prove a route is public (an unprotected
admin page is also the same for everyone), which is why the content itself
must look harmless too.

Like the other rules, this only reads the ast tree and the template files.
The scanned code is never run.
"""

import ast
import os
import re

from secureflow.constants import (
    ALLOWED_CALLS, ALLOWED_TEMPLATE_STATEMENTS, DATA_ACCESS_ATTRIBUTES, DATA_ACCESS_NAMES,
    PRIVILEGED_WORDS, PUBLIC_CONTENT_METHODS, REQUEST_STATE_ATTRIBUTES, REQUEST_STATE_NAMES,
    SENSITIVE_WORDS,
)
from secureflow.routes import METHOD_SHORTCUTS, last_name, lookup_object
from secureflow.rules import is_public

# The label written into protections_found for a route that passes.
PUBLIC_CONTENT_LABEL = "public_content:static_response"

# Jinja syntax in a template: {{ expression }} and {% statement %}.
JINJA_EXPRESSION = re.compile(r"\{\{")
JINJA_STATEMENT = re.compile(r"\{%[-+]?\s*(\w*)(.*?)[-+]?%\}", re.DOTALL)

# An extends/include chain longer than this is not followed (and not trusted).
MAX_TEMPLATE_DEPTH = 5


def add_public_content(routes, files, project_path):
    """Label every unprotected route that only returns fixed, harmless content.
    
    Only routes the missing-login rule would flag are looked at: a protected
    route or one on the public allowlist needs no second opinion.
    """
    for route in routes:
        if route.protections_found:
            continue  # already protected, nothing to decide
        if is_public(route) and not route.misplaced_protections:
            continue  # on the public allowlist, not flagged anyway
        if not_public_content_reason(route, files, project_path) is None:
            route.protections_found = [PUBLIC_CONTENT_LABEL]


def not_public_content_reason(route, files, project_path):
    """Why the route is NOT public content, as a short text, or None if it is.

    The checks run in order and the first one that fails is returned. Tests
    use the reason to check that the right rule stopped the route.
    """
    handler = route.handler
    if not isinstance(handler, ast.FunctionDef):
        return "handler is not a plain function"  # MethodView class, async def, unknown
    if not set(route.http_methods) <= PUBLIC_CONTENT_METHODS:
        return "accepts a method that is not GET, HEAD or OPTIONS"
    if "<" in route.url_path:
        return "path has a URL variable"
    if has_privileged_word(route.url_path) or has_privileged_word(handler.name):
        return "path or handler name has a privileged word"
    if not only_route_decorators(handler, route.file_path, files):
        return "has a decorator that is not a route decorator"
    if handler.args.args or handler.args.posonlyargs or handler.args.kwonlyargs \
            or handler.args.vararg or handler.args.kwarg:
        return "handler takes arguments"

    # The body: an optional docstring, then one `return <constant answer>`.
    body = handler.body
    if body and is_docstring(body[0]):
        body = body[1:]
    if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
        return "body is more than a single return"
    answer = body[0].value

    if uses_request_state(answer):
        return "uses request, session, g, current_user, cookies or headers"
    if uses_data_access(answer):
        return "uses the database, files, programs or the network"
    template_name = constant_answer_template(answer)
    if template_name is False:
        return "does not return a constant answer"

    texts = constant_texts(answer)
    if template_name:
        template_texts = read_template_chain(template_name, route, project_path)
        if template_texts is None:
            return "template is missing or has Jinja expressions or statements"
        texts += template_texts
    if any(has_sensitive_word(text) for text in texts):
        return "answer contains a sensitive word"
    return None


# ---------------------------------------------------------------------------
# Checks on the route and handler
# ---------------------------------------------------------------------------

def has_privileged_word(text):
    text = text.lower()
    return any(word in text for word in PRIVILEGED_WORDS)


def has_sensitive_word(text):
    text = text.lower()
    return any(word in text for word in SENSITIVE_WORDS)


def only_route_decorators(handler, file_path, files):
    """True if every decorator is `@x.route(...)` or `@x.get(...)` on a Flask app or Blueprint.

    Any other decorator (a cache, a rate limiter, a home-made check) may change
    what the route does, so the route is not public content.
    """
    info = files[file_path]
    for decorator in handler.decorator_list:
        if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)):
            return False
        if decorator.func.attr != "route" and decorator.func.attr not in METHOD_SHORTCUTS:
            return False
        if lookup_object(decorator.func.value.id, info, files) is None:
            return False
    return True


def is_docstring(statement):
    return (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str))


def uses_request_state(node):
    """True if the code mentions request, session, g, current_user, .cookies or .headers."""
    for part in ast.walk(node):
        if isinstance(part, ast.Name) and part.id in REQUEST_STATE_NAMES:
            return True
        if isinstance(part, ast.Attribute) and part.attr in REQUEST_STATE_ATTRIBUTES:
            return True
    return False


def uses_data_access(node):
    """True if the code mentions db, cursor, os, open, .execute, .query and the like."""
    for part in ast.walk(node):
        if isinstance(part, ast.Name) and part.id in DATA_ACCESS_NAMES:
            return True
        if isinstance(part, ast.Attribute) and (part.attr in DATA_ACCESS_ATTRIBUTES or last_name(part.value) in DATA_ACCESS_NAMES):
            return True
    return False


# ---------------------------------------------------------------------------
# Is the answer a constant?
# ---------------------------------------------------------------------------

def constant_answer_template(answer):
    """Check the returned value. Returns:

    - False if it is not one of the allowed constant answers;
    - the template file name for `render_template("x.html", ...)`;
    - None for any other allowed answer (text, bytes, jsonify({...})).

    `make_response(<answer>)` is unwrapped and checked the same way.
    """
    if is_constant_text(answer):
        return None
    if not isinstance(answer, ast.Call):
        return False
    called = last_name(answer.func)
    if called not in ALLOWED_CALLS:
        return False  # any other call may read data or do work, so it is not constant
    if called == "make_response":
        if len(answer.args) != 1 or answer.keywords:
            return False
        return constant_answer_template(answer.args[0])
    if called == "jsonify":
        if len(answer.args) == 1 and not answer.keywords and isinstance(answer.args[0], ast.Dict) \
                and is_constant_value(answer.args[0]):
            return None
        return False
    if called == "render_template":
        if len(answer.args) != 1 or not is_plain_string(answer.args[0]):
            return False
        if not all(keyword.arg and is_constant_value(keyword.value) for keyword in answer.keywords):
            return False
        return answer.args[0].value
    return False


def is_plain_string(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def is_constant_text(node):
    """A string, bytes, or an f-string with no {placeholders} (f"hello")."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
        return True
    if isinstance(node, ast.JoinedStr):
        return all(isinstance(part, ast.Constant) for part in node.values)
    return False


def is_constant_value(node):
    """A value that never changes: text, a number, True/False/None, a list,
    tuple or dict of such values, or url_for(...) with constant arguments."""
    if isinstance(node, ast.Constant) or is_constant_text(node):
        return True
    if isinstance(node, (ast.List, ast.Tuple)):
        return all(is_constant_value(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        # A key of None means `**other_dict`, which is not a constant.
        return all(key is not None and is_constant_value(key) for key in node.keys) \
            and all(is_constant_value(value) for value in node.values)
    if isinstance(node, ast.Call) and last_name(node.func) == "url_for":
        return all(is_constant_value(arg) for arg in node.args) \
            and all(keyword.arg and is_constant_value(keyword.value) for keyword in node.keywords)
    return False


def constant_texts(node):
    """All the text written in the answer, to look for sensitive words."""
    texts = []
    for part in ast.walk(node):
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            texts.append(part.value)
        elif isinstance(part, ast.Constant) and isinstance(part.value, bytes):
            texts.append(part.value.decode("utf-8", errors="replace"))
    return texts


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def template_folders(route, project_path):
    """Where Flask would look for templates: a `templates` folder next to the
    route's file, next to the file that creates its app or Blueprint, or at
    the project root. If the file is in none of them, the route is not
    public content (we could not read the page, so we do not trust it)."""
    folders = []
    for file_path in (route.file_path, route.owner.file_path if route.owner else route.file_path):
        folders.append(os.path.join(project_path, os.path.dirname(file_path), "templates"))
    folders.append(os.path.join(project_path, "templates"))
    return list(dict.fromkeys(folders))


def read_template_chain(name, route, project_path, depth=0):
    """The text of the template and every template it extends or includes.

    Returns None (not public content) when a file is missing, has a Jinja
    expression {{ }}, has a statement other than extends/block/endblock/include,
    or names another template in a way we cannot read.
    """
    if depth > MAX_TEMPLATE_DEPTH or ".." in name.split("/") or os.path.isabs(name):
        return None
    texts = []
    found = False
    # If the same name exists in several folders we read all of them, so a
    # wrong guess about which one Flask uses cannot make a route look safe.
    for folder in template_folders(route, project_path):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        found = True
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except (OSError, UnicodeDecodeError):
            return None
        if JINJA_EXPRESSION.search(text):
            return None
        texts.append(text)
        for match in JINJA_STATEMENT.finditer(text):
            keyword, rest = match.group(1), match.group(2).strip()
            if keyword not in ALLOWED_TEMPLATE_STATEMENTS:
                return None
            if keyword in ("extends", "include"):
                other = quoted_name(rest)
                if other is None:
                    return None
                other_texts = read_template_chain(other, route, project_path, depth + 1)
                if other_texts is None:
                    return None
                texts += other_texts
    return texts if found else None


def quoted_name(text):
    """`"base.html"` -> base.html. None if the text is anything else (a variable, a list...)."""
    match = re.fullmatch(r"""(["'])([^"']+)\1""", text)
    return match.group(2) if match else None
