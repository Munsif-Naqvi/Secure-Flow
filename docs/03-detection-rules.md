# Detection rules (midterm)

The engine reads Python files with the `ast` module. It never runs the scanned code. Skip folders: `venv`, `.venv`, `env`, `node_modules`, `__pycache__`, `.git`, `tests` of the scanned project is scanned normally. A file with a syntax error is skipped and listed in `files_skipped` with the reason.

## 1. Finding routes
A route is a function decorated with one of:
- `@app.route("/path", methods=[...])` where `app` is a `Flask(...)` object
- `@bp.route("/path", ...)` where `bp` is a `Blueprint(...)`. If the Blueprint is registered with `url_prefix` (in `Blueprint(..., url_prefix=...)` or `app.register_blueprint(bp, url_prefix=...)`), prepend it. If the prefix cannot be found, use the route path alone.
- `@app.get("/path")`, `@app.post(...)`, `.put`, `.delete`, `.patch` shortcuts
- `app.add_url_rule("/path", view_func=fn, methods=[...])`
Record: `url_path`, `http_methods` (default `["GET"]`), `file_path`, `line_number` (line of the decorator), and the handler function node.

## 2. Detecting protections
A route is **protected** if any of the following is true. Record what was found in `protections_found`.

a. **Decorator.** A decorator on the handler whose name (the last part of a dotted name, case-insensitive) is one of: `login_required`, `jwt_required`, `fresh_jwt_required`, `token_required`, `auth_required`, `admin_required`, `roles_required`, `role_required`, `permission_required`, `requires_auth`, `verify_jwt_in_request`, `login_manager.login_required`. Also treat any decorator whose name contains `login`, `auth`, `admin`, `role`, `permission` or `jwt` as a protection (this guess is recorded as `custom_decorator:<name>`).

b. **Blueprint-wide hook.** If the route's Blueprint has a `@bp.before_request` function that contains a check (see d), all routes of that Blueprint are protected. Same for `@app.before_request`, unless it excludes specific endpoints (then only protect the others when this is easy to determine; otherwise mark the hook as `before_request_partial` and treat routes as protected).

c. **Class-based protection.** For `MethodView` classes, a `decorators = [login_required, ...]` list protects the class's routes.

d. **Inline checks** inside the handler body or a before_request body: any of
   - a reference to `current_user.is_authenticated` or `current_user.is_active`
   - an `if` that tests the session for a user key (`session.get("user_id")`, `session["user"]`, `"user_id" in session`; key name containing `user`, `uid`, `login`, `auth` or `token`) and, in either branch, turns the visitor away: a `return redirect(...)`, an `abort(...)`, a `raise`, or an error answer such as `return "...", 401` (or 403). Only reading the user from the session, as in `user_id = session.get("user_id", 1)`, is not a check, because it does not stop anyone. (Tightened in Step 6, after the corpus showed two such misses; see `docs/results-midterm.md`.)
   - a call to `abort(401)` or `abort(403)`
   - a `redirect` to a URL whose text contains `login` inside an `if` that tests the session or current_user
   - `get_jwt_identity()` or `verify_jwt_in_request()`
   - `request.headers.get("Authorization")` tested in an `if`

If none apply, the route is **unprotected**.

**Decorator order matters.** Python applies decorators from the bottom up, and `@app.route` saves the view at the moment it runs. So only decorators *below* `@app.route` (or `@bp.route`, `@app.get`, ...) protect the route. A `@login_required` written *above* the route decorator wraps the function after Flask has already saved it, so Flask ignores it and the route is unprotected. The engine keeps such misplaced protection decorators so the finding can say so (see part 3). For `add_url_rule(..., view_func=fn)` every decorator on `fn` counts, because Flask receives the function after all of them were applied.

## 3. The rule: missing login (`missing_login`)
Flag every unprotected route except the **public allowlist**. A route is public if its path (lowercased, trailing slash removed) is one of: `/`, `/index`, `/home`, `/login`, `/signin`, `/logout`, `/register`, `/signup`, `/forgot-password`, `/reset-password`, `/health`, `/healthz`, `/ping`, `/about`, `/contact`, `/static/...`, `/favicon.ico`; or the handler function name is one of `index`, `home`, `login`, `logout`, `register`, `signup`, `health`, `static`. Keep the list in one constants file so it is easy to change.

**Severity:** High if the route accepts POST, PUT, PATCH or DELETE, or its path contains `admin`; otherwise Medium.

**Finding fields:** see `docs/04-findings.schema.json`.
- `problem_class`: `access_control`, `problem_type`: `missing_login`
- `finding_status`: `unconfirmed`
- `finding_match_key`: the first 12 hex characters of SHA-1 of `"<url_path>|<problem_type>|<file_path>"`
- `explanation`, plain language, filled from this template:
  `This route (<METHODS> <url_path>) has no login check that SecureFlow could find. Anyone who visits it may be able to use it without logging in. This was found by reading the code and has not been tested live.`

  `<METHODS>` is the route's methods joined with `, ` (for example `GET, POST`).
  If a protection decorator sits above the route decorator (see part 2), one sentence is added after the first one: `A @login_required sits above the route decorator, so Flask ignores it; move it below.` The decorator is named as written in the code. With more than one: `@login_required, @roles_required('admin') sit above the route decorator, so Flask ignores them; move them below.`

**Misplaced decorator on a public route.** A route with a protection decorator above its route decorator is flagged even when it is on the public allowlist, because the decorator shows the developer wanted a login check there. Rewriting the code automatically is a fix suggestion and stays post-midterm.

## 4. Honest limits (state these in the UI and the demo)
- **Database-backed public pages are flagged.** A route that reads the database is never treated as public content (part 6), even if it only reads a shared table such as a product list. The code stage cannot tell whether a table is owned by users, so such pages stay flagged (Unconfirmed). The live stage (FYP-2) resolves them by checking what the response contains and whether the tables are user-owned (`docs/08-verification-design.md`). In the corpus these routes are listed under `known_limitations`.
- The tool guesses from the code. It can flag a route that is protected in a way it cannot see (for example a protection added by a library at the web server level).
- It cannot yet tell whether a route *should* be public, beyond the allowlist and the strict public content rule (part 6).
- This is why every result is Unconfirmed in FYP-1.

## 5. Stretch rule: SQL injection (`sql_injection`)
Flag a call to `.execute(...)`, `.executemany(...)` or `text(...)` whose first argument is an f-string, a `%` formatting, a `.format()` call or a `+` concatenation that includes a value coming from `request.args`, `request.form`, `request.json`, `request.values`, `request.get_json()` or a route parameter, either directly or through a local variable assigned from one of these in the same function. Severity High. Not flagged: queries with `?` or `%s` placeholders and a separate parameter tuple.

## 6. Public content (`public_content:static_response`)
Some routes have no login check because they need none: they give the same harmless text to everyone. This rule recognises them by what the handler **does**, not by the route's name, so it works for apps with hundreds of routes. It is strict on purpose: a page that is the same for everyone is not proof that it is public (an open admin page is also the same for everyone), so when unsure, the route is still flagged.

It is applied only to routes the missing-login rule would flag (unprotected and not on the public allowlist). A route is **public content** only when **all** of these are true:

1. It answers only `GET`, `HEAD` or `OPTIONS`.
2. Its path has no URL variables (no `<...>`).
3. Its only decorators are route decorators (`@app.route`, `@bp.get`, ...). Any other decorator might change what the route does.
4. The handler is a plain function with no arguments, and its body is one `return` (a docstring before it is allowed). Anything more (a variable, an `if`, a loop) is not trusted.
5. It does not mention `request`, `session`, `g`, `current_user`, `.cookies` or `.headers`.
6. It does not mention the database, files, programs or the network (`db`, `cursor`, `connection`, `os`, `subprocess`, `open`, `.execute`, `.executemany`, `.query`, `.commit`, ...), and calls nothing except `render_template`, `jsonify`, `url_for` and `make_response`, all with constant arguments. A call to any other function, including the project's own, means "not public content".
7. It returns a constant: a string or bytes, an f-string without placeholders (`f"Open 9 to 5"`), `jsonify({...})` of a dict of constants, `render_template("x.html")` with no keyword arguments or only constant ones, or `make_response(...)` around one of these.
8. For a template: the file is found in a `templates` folder (next to the route's file, next to the file that creates its app or Blueprint, or at the project root). It must contain no `{{ }}` expression and no `{% %}` statement other than `extends`, `block`, `endblock` and `include`. Templates it extends or includes are checked the same way. A missing file means "not public content".
9. The returned text and the template text contain none of: `password`, `passwd`, `secret`, `token`, `api_key`, `apikey`, `private`, `admin`, `credential` (any case).
10. Neither the path nor the handler name contains a privileged word: `admin`, `export`, `download`, `dump`, `backup`, `delete`, `remove`, `debug`, `config`, `internal`, `manage`, `users`.

A route that passes is not flagged. It is still listed under `routes`, with `protections_found: ["public_content:static_response"]`, so the developer can see the decision. All word lists are in `engine/secureflow/constants.py`.

**A route that reads the database is never public content**, even if it only reads a shared table such as a product list. See part 4.

## Later rules (FYP-1 second half, not now)
Missing role check, access to another user's data (missing ownership check), command injection, path traversal, template injection.
