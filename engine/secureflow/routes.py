"""Finding Flask routes by reading the code (rules in docs/03-detection-rules.md, part 1).

We read each Python file with the standard-library `ast` module, which turns
source code into a tree of objects (an "abstract syntax tree"). We only look
at that tree. The scanned project's code is never imported or run.

The work happens in two passes over the project:

1. Collect, for every file, which variables hold a Flask app or a Blueprint,
   what each file imports, and every `register_blueprint(...)` call.
2. Go through every file again and read the routes: the `@x.route(...)`,
   `@x.get(...)` style decorators and `x.add_url_rule(...)` calls, where `x`
   is a Flask app or Blueprint found in pass 1.

Anything we cannot work out from plain text in the code (for example a URL
built by calling a function) is skipped instead of guessed.
"""

import ast
import os
from dataclasses import dataclass, field

# `@app.get("/x")` and friends: decorator name -> the one HTTP method it means.
METHOD_SHORTCUTS = {"get": "GET", "post": "POST", "put": "PUT", "delete": "DELETE", "patch": "PATCH"}

# Method names Flask looks for on a MethodView class.
METHOD_VIEW_FUNCTIONS = ["get", "post", "put", "delete", "patch"]


@dataclass(eq=False)  # eq=False: each object is its own dict key, compared by identity
class FlaskObject:
    """A variable that holds `Flask(...)` or `Blueprint(...)`."""
    kind: str             # "app" or "blueprint"
    name: str             # the variable name, e.g. "admin_bp"
    file_path: str        # file where it is created
    url_prefix: str = ""  # from Blueprint(..., url_prefix="...") if given


@dataclass
class Route:
    """One route. The fields after line_number are used by protections.py and rules.py, not printed."""
    url_path: str
    http_methods: list
    file_path: str
    line_number: int
    handler: object = None     # ast node of the function (or MethodView class)
    owner: object = None       # the FlaskObject (app or Blueprint) the route is on
    # The decorators that really wrap the view Flask calls. Python applies
    # decorators from the bottom up, so for `@x.route` only the ones *below*
    # it count: one above it is added after Flask has already saved the view.
    decorators: list = field(default_factory=list)
    # The decorators *above* `@x.route`. Flask ignores them, so they never
    # protect the route. rules.py uses them to warn about a misplaced
    # @login_required. Always empty for add_url_rule routes.
    decorators_above: list = field(default_factory=list)
    protections_found: list = field(default_factory=list)
    misplaced_protections: list = field(default_factory=list)  # filled by protections.py

    def to_dict(self):
        """The route in the JSON format of docs/04-findings.schema.json."""
        return {
            "url_path": self.url_path,
            "http_methods": self.http_methods,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "protections_found": self.protections_found,
        }


@dataclass
class FileInfo:
    """What pass 1 learned about one file."""
    file_path: str
    tree: ast.Module
    constants: dict = field(default_factory=dict)    # NAME = "text" at the top of the file
    objects: dict = field(default_factory=dict)      # variable name -> FlaskObject
    imports: dict = field(default_factory=dict)      # local name -> (module path, original name)
    functions: dict = field(default_factory=dict)    # function name -> ast node
    classes: dict = field(default_factory=dict)      # class name -> ast node


def parse_files(project_path, python_files):
    """Parse each file into an ast tree. Files that cannot be parsed are skipped.

    Returns (trees, skipped): trees maps file_path -> tree, skipped is the
    list for the `files_skipped` field of the output.
    """
    trees = {}
    skipped = []
    for file_path in python_files:
        disk_path = os.path.join(project_path, file_path)
        try:
            with open(disk_path, "rb") as handle:
                source = handle.read()
            # Giving ast.parse the raw bytes lets Python honour any
            # "# -*- coding: ... -*-" line at the top of the file.
            trees[file_path] = ast.parse(source, filename=file_path)
        except SyntaxError as error:
            skipped.append({"file_path": file_path, "reason": "syntax error on line " + str(error.lineno)})
        except (OSError, ValueError) as error:
            skipped.append({"file_path": file_path, "reason": "could not read file: " + str(error)})
    return trees, skipped


def collect_files(trees):
    """Pass 1 for every parsed file. Returns a dict: file_path -> FileInfo."""
    return {file_path: collect_file_info(file_path, tree) for file_path, tree in trees.items()}


def find_routes(files):
    """Return the list of Route objects found in all files, in file and line order.

    `files` is the result of collect_files(trees).
    """
    registrations = collect_registrations(files)

    routes = []
    for info in files.values():
        routes.extend(routes_in_file(info, files, registrations))
    routes.sort(key=lambda route: (route.file_path, route.line_number))
    return routes


# ---------------------------------------------------------------------------
# Pass 1: what each file defines and imports
# ---------------------------------------------------------------------------

def collect_file_info(file_path, tree):
    info = FileInfo(file_path=file_path, tree=tree)

    # Only top-level statements: apps and blueprints are made at module level.
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if is_static_string(node.value):
                info.constants[name] = node.value.value
            flask_object = flask_object_from_call(node.value, name, file_path, info.constants)
            if flask_object:
                info.objects[name] = flask_object
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            info.classes[node.name] = node

    # Imports can sit anywhere (for example inside a create_app function).
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = resolve_module(file_path, node.module, node.level)
            for alias in node.names:
                info.imports[alias.asname or alias.name] = (module, alias.name)
    return info


def flask_object_from_call(value, name, file_path, constants):
    """If `value` is `Flask(...)` or `Blueprint(...)`, describe it, else return None."""
    if not isinstance(value, ast.Call):
        return None
    called = last_name(value.func)
    if called == "Flask":
        return FlaskObject("app", name, file_path)
    if called == "Blueprint":
        prefix = static_text(keyword_value(value, "url_prefix"), constants)
        return FlaskObject("blueprint", name, file_path, prefix or "")
    return None


def resolve_module(file_path, module, level):
    """Turn an import into a path without ".py", relative to the project.

    `from .admin import bp` in "shop/views.py" -> "shop/admin".
    `from shop.admin import bp` anywhere     -> "shop/admin".
    """
    parts = module.split(".") if module else []
    if level == 0:
        return "/".join(parts)
    # A relative import starts from the file's own folder, then goes up one
    # folder for each extra dot.
    folder = file_path.split("/")[:-1]
    if level > 1:
        folder = folder[: -(level - 1)]
    return "/".join(folder + parts)


def collect_registrations(files):
    """Find `x.register_blueprint(bp, url_prefix="...")` calls.

    Returns a dict: FlaskObject (the blueprint) -> url_prefix given at registration.
    """
    registrations = {}
    for info in files.values():
        for node in ast.walk(info.tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr != "register_blueprint" or not node.args:
                continue
            if not isinstance(node.args[0], ast.Name):
                continue  # e.g. register_blueprint(admin.bp): not supported yet
            blueprint = lookup_object(node.args[0].id, info, files)
            prefix = static_text(keyword_value(node, "url_prefix"), info.constants)
            if blueprint and blueprint.kind == "blueprint" and prefix is not None:
                registrations[blueprint] = prefix
    return registrations


def lookup_object(name, info, files):
    """Find the Flask app or Blueprint that the variable `name` means inside this file.

    Either it is created in this file, or it is imported from another file of
    the project. Returns None when we cannot tell (then it is not used).
    """
    if name in info.objects:
        return info.objects[name]
    if name not in info.imports:
        return None
    module, original_name = info.imports[name]

    # The import can point at "pkg/admin.py" or at the package "pkg/admin/__init__.py".
    # We also accept a path that ends with the module, for projects whose code
    # sits in a subfolder (e.g. "src/shop/admin.py" for "shop.admin").
    candidates = [module + ".py", module + "/__init__.py"]
    for other in files.values():
        path = other.file_path
        for candidate in candidates:
            if path == candidate or path.endswith("/" + candidate):
                if original_name in other.objects:
                    return other.objects[original_name]
    return None


# ---------------------------------------------------------------------------
# Pass 2: the routes themselves
# ---------------------------------------------------------------------------

def routes_in_file(info, files, registrations):
    routes = []
    for node in ast.walk(info.tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for index, decorator in enumerate(node.decorator_list):
                route = route_from_decorator(decorator, node, info, files, registrations)
                if route:
                    # decorator_list is in top-to-bottom order: split it at this one.
                    route.decorators = node.decorator_list[index + 1:]
                    route.decorators_above = node.decorator_list[:index]
                    routes.append(route)
        elif isinstance(node, ast.Call):
            route = route_from_add_url_rule(node, info, files, registrations)
            if route:
                routes.append(route)
    return routes


def route_from_decorator(decorator, function, info, files, registrations):
    """Read `@x.route("/path", methods=[...])` or `@x.get("/path")` on a function."""
    # A decorator with arguments is a call: @x.route(...) -> Call(func=Attribute(x, "route")).
    if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)):
        return None
    owner = decorator.func.value
    action = decorator.func.attr
    if not isinstance(owner, ast.Name) or (action != "route" and action not in METHOD_SHORTCUTS):
        return None
    flask_object = lookup_object(owner.id, info, files)
    if flask_object is None:
        return None

    path = static_text(first_argument(decorator, "rule"), info.constants)
    if path is None:
        return None  # URL is not plain text in the code, e.g. built by a function call

    if action == "route":
        methods = read_methods(keyword_value(decorator, "methods"), info.constants)
    else:
        methods = [METHOD_SHORTCUTS[action]]

    return Route(
        url_path=full_path(flask_object, path, registrations),
        http_methods=methods,
        file_path=info.file_path,
        line_number=decorator.lineno,
        handler=function,
        owner=flask_object,
    )


def route_from_add_url_rule(call, info, files, registrations):
    """Read `x.add_url_rule("/path", view_func=handler, methods=[...])`.

    Flask's signature is add_url_rule(rule, endpoint=None, view_func=None, **options),
    so the handler can also be the third positional argument.
    """
    if not (isinstance(call.func, ast.Attribute) and call.func.attr == "add_url_rule"):
        return None
    if not isinstance(call.func.value, ast.Name):
        return None
    flask_object = lookup_object(call.func.value.id, info, files)
    if flask_object is None:
        return None

    path = static_text(first_argument(call, "rule"), info.constants)
    view_func = keyword_value(call, "view_func")
    if view_func is None and len(call.args) >= 3:
        view_func = call.args[2]
    handler, class_methods = find_handler(view_func, info)
    if path is None or handler is None:
        return None  # we only report a route when both URL and handler are known

    methods_node = keyword_value(call, "methods")
    if methods_node is None and class_methods:
        methods = class_methods  # a MethodView answers the methods it defines
    else:
        methods = read_methods(methods_node, info.constants)

    # add_url_rule receives the function after all its decorators were applied,
    # so every decorator on it counts. A MethodView class keeps its decorators
    # in a `decorators = [...]` list instead, which protections.py reads.
    decorators = handler.decorator_list if isinstance(handler, (ast.FunctionDef, ast.AsyncFunctionDef)) else []
    return Route(
        url_path=full_path(flask_object, path, registrations),
        http_methods=methods,
        file_path=info.file_path,
        line_number=call.lineno,
        handler=handler,
        owner=flask_object,
        decorators=decorators,
    )


def find_handler(view_func, info):
    """Find the function (or MethodView class) given as view_func, in the same file.

    Returns (node, methods). `methods` is only filled for a MethodView class:
    `MyView.as_view("name")` answers the HTTP methods the class defines (get, post, ...).
    """
    if isinstance(view_func, ast.Name) and view_func.id in info.functions:
        return info.functions[view_func.id], None
    if (isinstance(view_func, ast.Call) and isinstance(view_func.func, ast.Attribute)
            and view_func.func.attr == "as_view" and isinstance(view_func.func.value, ast.Name)
            and view_func.func.value.id in info.classes):
        view_class = info.classes[view_func.func.value.id]
        defined = {item.name for item in view_class.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
        methods = [name.upper() for name in METHOD_VIEW_FUNCTIONS if name in defined]
        return view_class, methods or None
    return None, None


def full_path(flask_object, path, registrations):
    """Put the Blueprint's url_prefix in front of the route path, as Flask does.

    A prefix given to register_blueprint wins over the one in Blueprint(...).
    If no prefix can be found, the route path is used alone.
    """
    if flask_object.kind != "blueprint":
        return path
    prefix = registrations.get(flask_object, flask_object.url_prefix)
    if not prefix:
        return path
    if not path:
        return prefix
    return prefix.rstrip("/") + "/" + path.lstrip("/")


def read_methods(node, constants):
    """Read `methods=["GET", "POST"]`. Defaults to ["GET"] when missing or unreadable."""
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return ["GET"]
    methods = []
    for item in node.elts:
        text = static_text(item, constants)
        if text is not None and text.upper() not in methods:
            methods.append(text.upper())
    return methods or ["GET"]


# ---------------------------------------------------------------------------
# Small helpers for reading ast nodes
# ---------------------------------------------------------------------------

def is_static_string(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def static_text(node, constants):
    """The text of a plain string, or of a top-level NAME = "text" constant. Else None."""
    if is_static_string(node):
        return node.value
    if isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id]
    return None


def keyword_value(call, name):
    """The value of keyword argument `name` in a call, or None."""
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def first_argument(call, keyword_name):
    """The first positional argument, or the keyword argument with that name."""
    if call.args:
        return call.args[0]
    return keyword_value(call, keyword_name)


def last_name(node):
    """`Flask` for both `Flask(...)` and `flask.Flask(...)`."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None
