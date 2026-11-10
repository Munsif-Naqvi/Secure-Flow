"""The missing-ownership-check rule, also called IDOR (docs/03-detection-rules.md, part 10).

IDOR means "Insecure Direct Object Reference": the visitor picks which record
to open (for example `/user/profile?id=2`), and the app opens it without
checking that the record belongs to the visitor. User A can then read or
change User B's data just by changing the number.

A login-protected route is flagged when, in its handler:
1. a database query (`.execute(...)`) reads or changes a table whose rows
   belong to users (the users table itself, or a table with an owner column
   such as `user_id`), found from the CREATE TABLE statements in the project;
2. a value the visitor chooses (from the URL path, query string, form or JSON
   body) goes into that query;
3. nothing ties the query to the logged-in user: no session or current_user
   value in the query, no `if <record owner> != <logged-in user>: <turn away>`
   check, and no owner-style decorator.

Like the other rules, this only reads the code. Every finding is "unconfirmed".
"""

import ast
import os
import re

from secureflow.constants import (
    LOGIN_STATE_ATTRIBUTES, OWNER_COLUMNS, OWNER_DECORATOR_WORDS, USER_TABLE_NAMES, VISITOR_SOURCES,
)
from secureflow.protections import SESSION_USER_WORDS, turns_visitor_away, walk_list
from secureflow.role_check import is_login_protected
from secureflow.routes import last_name, static_text
from secureflow.rules import match_key

# Folders whose .sql files are not the developer's own schema.
SKIPPED_FOLDERS = {".git", ".venv", "venv", "env", "__pycache__", "node_modules", ".secureflow"}


def missing_ownership_findings(routes, files, project_path):
    """Return the missing_ownership_check findings, in the same order as `routes`."""
    tables = user_owned_tables(files, project_path)
    findings = []
    for route in routes:
        if not is_login_protected(route) or has_owner_decorator(route):
            continue
        query = unchecked_query(route, tables)
        if query is not None:
            findings.append(make_finding(route, query))
    return findings


# ---------------------------------------------------------------------------
# Step 1: which tables hold rows that belong to users?
# ---------------------------------------------------------------------------

CREATE_TABLE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?(\w+)[\"`\]]?\s*\(", re.IGNORECASE)
# Lines inside CREATE TABLE ( ... ) that are rules about the table, not columns.
CONSTRAINT_WORDS = {"primary", "foreign", "unique", "check", "constraint", "key", "index"}


def user_owned_tables(files, project_path):
    """{table name (lower case): why its rows belong to users}, from every CREATE TABLE.

    The CREATE TABLE text is looked for in the strings of every Python file
    (as in `cursor.execute("CREATE TABLE ...")`) and in .sql files.
    """
    texts = []
    for info in files.values():
        for node in ast.walk(info.tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and "create" in node.value.lower():
                texts.append(node.value)
    texts += sql_files(project_path)

    tables = {}
    for text in texts:
        for name, columns_text in create_tables(text):
            reason = owner_reason(name, columns_text)
            if reason:
                tables[name.lower()] = (name, reason)
    return tables


def sql_files(project_path):
    """The text of every .sql file in the project (for example schema.sql)."""
    texts = []
    for folder, subfolders, names in os.walk(project_path):
        subfolders[:] = [name for name in subfolders if name not in SKIPPED_FOLDERS]
        for name in names:
            if name.lower().endswith(".sql"):
                try:
                    with open(os.path.join(folder, name), encoding="utf-8", errors="replace") as handle:
                        texts.append(handle.read())
                except OSError:
                    pass  # an unreadable schema file only means fewer tables are known
    return texts


def create_tables(text):
    """[(table name, text between the brackets)] for each CREATE TABLE in the text."""
    found = []
    for match in CREATE_TABLE.finditer(text):
        # Find the bracket that closes the column list. Brackets can nest,
        # as in `price DECIMAL(10, 2)` or `REFERENCES users(id)`.
        depth = 1
        position = match.end()
        while position < len(text) and depth > 0:
            depth += {"(": 1, ")": -1}.get(text[position], 0)
            position += 1
        found.append((match.group(1), text[match.end():position - 1]))
    return found


def split_columns(columns_text):
    """Split "a INT, b DECIMAL(10, 2), ..." on the commas that are not inside brackets."""
    parts, depth, current = [], 0, ""
    for character in columns_text:
        if character == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        depth += {"(": 1, ")": -1}.get(character, 0)
        current += character
    parts.append(current)
    return [part.strip() for part in parts if part.strip()]


def owner_reason(table_name, columns_text):
    """Why rows of this table belong to users, as a sentence part for the explanation, or None."""
    if table_name.lower() in USER_TABLE_NAMES:
        return "Each row of that table is one user's data"
    for part in split_columns(columns_text):
        words = part.replace("`", " ").replace('"', " ").replace("(", " ").replace(")", " ").split()
        if not words:
            continue
        column = words[0].lower()
        lowered = part.lower()
        # A column that points to the users table, e.g. "author INTEGER REFERENCES users(id)".
        references_users = any(re.search(r"references\s+[\"`\[]?" + name + r"\b", lowered) for name in USER_TABLE_NAMES)
        if column in CONSTRAINT_WORDS:
            # "FOREIGN KEY (author_id) REFERENCES users(id)": words[2] is the column.
            if column == "foreign" and references_users and len(words) > 2:
                return "In that table the " + words[2] + " column points to the users table, so each row belongs to a user"
            continue
        if references_users:
            return "In that table the " + words[0] + " column points to the users table, so each row belongs to a user"
        if column in OWNER_COLUMNS:
            return "In that table the " + words[0] + " column says which user owns each row"
    return None


# ---------------------------------------------------------------------------
# Step 2: which values in the handler come from the visitor, which from the session?
# ---------------------------------------------------------------------------

def visitor_source(node, url_variables, visitor_names):
    """(key, place) if this expression contains a value the visitor chooses, else None.

    For example request.args.get("id") -> ("id", "from the query string"),
    and a URL variable post_id -> ("post_id", "in the URL path").
    `visitor_names` maps variables already known to hold such a value to their (key, place).
    """
    for part in ast.walk(node):
        # data.get("id") or data["id"], where data is request.form, request.get_json(), ...
        container, key = keyed_read(part)
        if container is not None:
            place = visitor_place(container, url_variables, visitor_names)
            if place is not None:
                return (key or place[0]), place[1]
        place = visitor_place(part, url_variables, visitor_names)
        if place is not None:
            return place
    return None


def visitor_place(node, url_variables, visitor_names):
    """(key or None, place) if node itself is a visitor value: request.args, a URL variable, ..."""
    if isinstance(node, ast.Name):
        if node.id in url_variables:
            return node.id, "in the URL path"
        return visitor_names.get(node.id)
    if isinstance(node, ast.Attribute) and node.attr in VISITOR_SOURCES and last_name(node.value) == "request":
        return None, VISITOR_SOURCES[node.attr]
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get_json"
            and last_name(node.func.value) == "request"):
        return None, VISITOR_SOURCES["json"]
    return None


def keyed_read(node):
    """(container, key text) for x.get("key") or x["key"], else (None, None)."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args:
        return node.func.value, static_text(node.args[0], {})
    if isinstance(node, ast.Subscript):
        return node.value, static_text(node.slice, {})
    return None, None


def describe_source(source):
    """("id", "from the query string") -> "id from the query string"."""
    key, place = source
    return (key + " " if key else "a value ") + place


def is_session_user(node, session_names):
    """True if the expression contains the logged-in user's identity:
    session["user_id"], session.get("user_id"), current_user.id, g.user,
    get_jwt_identity(), or a variable set from one of these.

    current_user.is_authenticated and similar only say *whether* someone is
    logged in, not *who*, so they do not count.
    """
    current_user_names = 0   # how often `current_user` appears
    login_state_reads = 0    # how often as current_user.is_authenticated (or similar)
    for part in ast.walk(node):
        if isinstance(part, ast.Name) and part.id in session_names:
            return True
        if isinstance(part, ast.Name) and part.id == "current_user":
            current_user_names += 1
        if isinstance(part, ast.Call) and last_name(part.func) == "get_jwt_identity":
            return True
        if isinstance(part, ast.Attribute):
            if last_name(part.value) == "current_user" and part.attr in LOGIN_STATE_ATTRIBUTES:
                login_state_reads += 1
            if last_name(part.value) == "g" and "user" in part.attr.lower():
                return True
        if session_user_key(part) is not None:
            return True
    # current_user.id, current_user, current_user.username ... but not only current_user.is_authenticated.
    return current_user_names > login_state_reads


def session_user_key(node):
    """The key in session["user_id"] or session.get("user_id") when it names a user, else None."""
    key = None
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
            and last_name(node.func.value) == "session" and node.args):
        key = static_text(node.args[0], {})
    elif isinstance(node, ast.Subscript) and last_name(node.value) == "session":
        key = static_text(node.slice, {})
    if key is not None and any(word in key.lower() for word in SESSION_USER_WORDS):
        return key
    return None


def sort_variables(function, url_variables):
    """Look at every `name = ...` in the handler and sort the names.

    Returns (visitor_names, session_names):
    - visitor_names: {name: description} for variables that can hold a value the
      visitor chose. One such assignment is enough, as in
          requested_id = request.args.get("id")
          if not requested_id:
              requested_id = session["user_id"]
      where the visitor can still choose the id.
    - session_names: variables that only ever hold the logged-in user's identity.
    """
    assignments = []
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            assignments.append((node.targets[0].id, node.value))

    visitor_names, session_like = {}, set()
    # Repeat a few times so `a = request.args["id"]; b = int(a)` marks b too.
    for _ in range(3):
        for name, value in assignments:
            source = visitor_source(value, url_variables, visitor_names)
            if source is not None and name not in visitor_names:
                visitor_names[name] = source
            elif is_session_user(value, session_like):
                session_like.add(name)
    session_names = session_like - set(visitor_names)
    return visitor_names, session_names


# ---------------------------------------------------------------------------
# Step 3: find a query on a user-owned table that the visitor controls
# ---------------------------------------------------------------------------

def unchecked_query(route, tables):
    """The first unchecked query as ((table, reason), visitor value text, changes data), or None."""
    function = route.handler
    if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    url_variables = {argument.arg for argument in function.args.args} & set(re.findall(r"<(?:\w+:)?(\w+)>", route.url_path))
    visitor_names, session_names = sort_variables(function, url_variables)
    if has_ownership_if(function, session_names):
        return None

    for node in ast.walk(function):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("execute", "executemany") and node.args):
            continue
        sql = sql_text(node.args[0], function)
        kind = sql.split()[0].upper() if sql.split() else ""
        if kind not in ("SELECT", "UPDATE", "DELETE"):
            continue  # INSERT adds a new row; it does not open someone else's
        reason = next((tables[name.lower()] for name in query_tables(sql) if name.lower() in tables), None)
        if reason is None:
            continue
        # Everything that can put a value into the query: the parameters, and
        # any {...} or + parts of the SQL text itself.
        values = list(node.args[1:]) + [keyword.value for keyword in node.keywords] + [node.args[0]]
        if any(is_session_user(value, session_names) for value in values):
            continue  # the query is tied to the logged-in user, e.g. "... AND user_id = ?"
        sources = [visitor_source(part, url_variables, visitor_names)
                   for value in values for part in parts_of(value)]
        sources = [source for source in sources if source is not None]
        if sources:
            # Name the value that most likely picks the record: one called "id" or "..._id".
            id_like = [source for source in sources if source[0] and "id" in source[0].lower()]
            return reason, describe_source((id_like or sources)[0]), kind != "SELECT"
    return None


def parts_of(value):
    """The items of a tuple or list of query parameters, or the value itself."""
    if isinstance(value, (ast.Tuple, ast.List)):
        return value.elts
    return [value]


def sql_text(node, function):
    """The plain text parts of the SQL. A variable is followed to its `sql = "..."` in the handler."""
    if isinstance(node, ast.Name):
        for statement in ast.walk(function):
            if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == node.id):
                return sql_text(statement.value, function)
        return ""
    pieces = [part.value for part in ast.walk(node) if isinstance(part, ast.Constant) and isinstance(part.value, str)]
    return " ".join(pieces).strip()


def query_tables(sql):
    """The table names after FROM, JOIN and UPDATE in the SQL text."""
    return re.findall(r"\b(?:FROM|JOIN|UPDATE)\s+[\"`\[]?(\w+)", sql, re.IGNORECASE)


def has_ownership_if(function, session_names):
    """True if the handler has `if <compare with the logged-in user>: <turn away>`, for example
        if note["user_id"] != session["user_id"]:
            abort(403)
    """
    for node in walk_list(function.body):
        if isinstance(node, ast.If) and compares_with_session_user(node.test, session_names):
            if turns_visitor_away(node.body) or turns_visitor_away(node.orelse):
                return True
    return False


def compares_with_session_user(test, session_names):
    """True if the test has `a == b`, `a != b`, `a is b` or `a is not b` where one
    side is the logged-in user and the other side is something else."""
    for node in ast.walk(test):
        if not isinstance(node, ast.Compare):
            continue
        if not all(isinstance(op, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)) for op in node.ops):
            continue
        sides = [node.left] + node.comparators
        user_sides = [side for side in sides if is_session_user(side, session_names)]
        # The other side must be a record value, not a fixed value: comparing the
        # session with None (`if session.get("user_id") is None`) is a login check.
        other_sides = [side for side in sides if side not in user_sides and not isinstance(side, ast.Constant)]
        if user_sides and other_sides:
            return True
    return False


def has_owner_decorator(route):
    """True if a decorator that wraps the view has "owner" in its name, e.g. @owner_required."""
    for decorator in route.decorators:
        name = last_name(decorator.func if isinstance(decorator, ast.Call) else decorator) or ""
        if any(word in name.lower() for word in OWNER_DECORATOR_WORDS):
            return True
    return False


# ---------------------------------------------------------------------------
# The finding
# ---------------------------------------------------------------------------

def explanation(route, query):
    (table, reason), source, changes_data = query
    methods = ", ".join(route.http_methods)
    action = "changes a record in" if changes_data else "reads a record from"
    harm = "change or delete" if changes_data else "see"
    return (
        "This route (" + methods + " " + route.url_path + ") checks that the visitor is logged in, but it "
        + action + " the " + table + " table using a value the visitor chooses (" + source + "). "
        + reason + ", and SecureFlow found no check that the record belongs to the visitor. "
        "A logged-in user may be able to " + harm + " another user's data by changing that value. "
        "This was found by reading the code and has not been tested live."
    )


def make_finding(route, query):
    """One finding in the format of docs/04-findings.schema.json."""
    return {
        "finding_match_key": match_key(route.url_path, "missing_ownership_check", route.file_path),
        "problem_class": "access_control",
        "problem_type": "missing_ownership_check",
        "severity": "High",  # another user's private data, or a change to it
        "finding_status": "unconfirmed",
        "url_path": route.url_path,
        "file_path": route.file_path,
        "line_number": route.line_number,
        "explanation": explanation(route, query),
    }
