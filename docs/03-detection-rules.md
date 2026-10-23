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
   - `session` read for a user key: `session.get("user_id")`, `session["user"]`, `"user_id" in session` (key name containing `user`, `uid`, `login`, `auth` or `token`)
   - a call to `abort(401)` or `abort(403)`
   - a `redirect` to a URL whose text contains `login` inside an `if` that tests the session or current_user
   - `get_jwt_identity()` or `verify_jwt_in_request()`
   - `request.headers.get("Authorization")` tested in an `if`

If none apply, the route is **unprotected**.

## 3. The rule: missing login (`missing_login`)
Flag every unprotected route except the **public allowlist**. A route is public if its path (lowercased, trailing slash removed) is one of: `/`, `/index`, `/home`, `/login`, `/signin`, `/logout`, `/register`, `/signup`, `/forgot-password`, `/reset-password`, `/health`, `/healthz`, `/ping`, `/about`, `/contact`, `/static/...`, `/favicon.ico`; or the handler function name is one of `index`, `home`, `login`, `logout`, `register`, `signup`, `health`, `static`. Keep the list in one constants file so it is easy to change.

**Severity:** High if the route accepts POST, PUT, PATCH or DELETE, or its path contains `admin`; otherwise Medium.

**Finding fields:** see `docs/04-findings.schema.json`.
- `problem_class`: `access_control`, `problem_type`: `missing_login`
- `finding_status`: `unconfirmed`
- `finding_match_key`: the first 12 hex characters of SHA-1 of `"<url_path>|<problem_type>|<file_path>"`
- `explanation`, plain language, filled from this template:
  `This route (<METHODS> <url_path>) has no login check that SecureFlow could find. Anyone who visits it may be able to use it without logging in. This was found by reading the code and has not been tested live.`

## 4. Honest limits (state these in the UI and the demo)
- The tool guesses from the code. It can flag a route that is protected in a way it cannot see (for example a protection added by a library at the web server level).
- It cannot yet tell whether a route *should* be public beyond the allowlist.
- This is why every result is Unconfirmed in FYP-1.

## 5. Stretch rule: SQL injection (`sql_injection`)
Flag a call to `.execute(...)`, `.executemany(...)` or `text(...)` whose first argument is an f-string, a `%` formatting, a `.format()` call or a `+` concatenation that includes a value coming from `request.args`, `request.form`, `request.json`, `request.values`, `request.get_json()` or a route parameter, either directly or through a local variable assigned from one of these in the same function. Severity High. Not flagged: queries with `?` or `%s` placeholders and a separate parameter tuple.

## Later rules (FYP-1 second half, not now)
Missing role check, access to another user's data (missing ownership check), command injection, path traversal, template injection.
